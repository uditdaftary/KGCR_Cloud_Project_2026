"""Review mode end to end (FD-01 S1b to S5), run locally.

estate -> graph -> reconstructed intent (P8) -> recommended options (P7) ->
advisor loop (P6) -> explanation (P9) -> stored artifacts.

The estate is *harvested* from the synthetic corpus, standing in for AWS Config:
the target is drawn from the held-out test split and defect-injected, so neither
the reconstructor nor the recommender has seen it. Both models are fitted on the
train+validation split only, in seconds and deterministically, so nothing is
unpickled.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from kgcr.advisor.advisor import Advisor, AdvisorFinding
from kgcr.advisor.controls import DRAFT_CONTROLS_PATH
from kgcr.advisor.llm import DEFAULT_FIXTURE_DIR, GEMINI_MODEL, FixtureClient, live_client_from_env
from kgcr.advisor.loop import LoopResult, TemplatePatcher, advisor_loop, spec_hash
from kgcr.corpus.estate import Estate
from kgcr.corpus.graph import build_graph_from_estate
from kgcr.corpus.pipeline import generate_corpus
from kgcr.corpus.splits import split_estates
from kgcr.defects.inject import DefectedEstate, applicable_injectors
from kgcr.defects.pipeline import inject_corpus
from kgcr.explainer.explainer import AUDIENCES, ExplanationBundle, build_bundle, bundle_json, render
from kgcr.orchestration.aws import ArtifactStore, Notifier
from kgcr.recommender.recommender import (
    OptionRecommender,
    RankedOption,
    estate_options,
    intent_from_reconstruction,
)
from kgcr.reconstruction.pipeline import ESCALATION_THRESHOLD
from kgcr.reconstruction.reconstructor import IntentReconstructor, ReconstructedIntent
from kgcr.repro import seed_everything
from kgcr.runrecord import RunRecord

__all__ = ["ReviewRun", "select_target", "run_review"]


@dataclass(frozen=True, slots=True)
class ReviewRun:
    """Everything one review produced, for printing and for tests."""

    target: DefectedEstate
    graph_nodes: int
    graph_edges: int
    intent: ReconstructedIntent
    escalated: tuple[str, ...]
    recommended: tuple[RankedOption, ...]
    missing_from_estate: tuple[tuple[str, str, str], ...]
    unexpected_in_estate: tuple[tuple[str, str, str], ...]
    llm_mode: str
    loop: LoopResult
    reviewed_findings: tuple[AdvisorFinding, ...]
    bundle: ExplanationBundle
    record: RunRecord
    artifacts: dict[str, str]


def select_target(test: list[Estate], variant: str) -> DefectedEstate:
    """The first held-out estate (by id) that ``variant`` can be injected into."""
    for estate in sorted(test, key=lambda e: e.estate_id):
        for injector in applicable_injectors(estate):
            if injector.variant == variant:
                return injector.run(estate)
    raise ValueError(f"no held-out estate admits variant {variant!r}")


def _graph_version() -> str:
    digest = hashlib.sha256(DRAFT_CONTROLS_PATH.read_bytes()).hexdigest()[:12]
    return f"l1-draft-{digest}"


def run_review(
    *,
    variant: str,
    store: ArtifactStore,
    notifier: Notifier,
    count: int = 180,
    seed: int = 1729,
) -> ReviewRun:
    seed_everything(seed)
    corpus = generate_corpus(count, seed)
    split = split_estates(corpus)
    by_id = {e.estate_id: e for e in corpus}
    fit = [by_id[i] for i in (*split.train.estate_ids, *split.validation.estate_ids)]
    target = select_target([by_id[i] for i in split.test.estate_ids], variant)
    estate = target.estate

    # S1b harvest is the corpus stand-in above; S1c reconstruct intent (P8).
    graph = build_graph_from_estate(estate)
    reconstructor = IntentReconstructor(random_state=0)
    reconstructor.fit(fit)
    intent = reconstructor.reconstruct(estate)
    escalated = tuple(sorted(intent.low_confidence_fields(ESCALATION_THRESHOLD)))
    intent_values = intent_from_reconstruction(intent)

    # S2 recommend (P7): what this intent should look like, versus what is there.
    recommender = OptionRecommender(random_state=0)
    recommender.fit(fit, [d.estate for d in inject_corpus(fit)])
    recommended = tuple(recommender.recommend(intent_values))
    wanted = {r.option for r in recommended if r.score >= 0.5}
    observed = estate_options(estate)

    # S3 advisor loop (P6). Gemini replays fixtures; without one the advisor
    # logs a warning and runs the rule floor only (strict_llm=False).
    live = live_client_from_env()
    llm = FixtureClient(DEFAULT_FIXTURE_DIR, live) if live or DEFAULT_FIXTURE_DIR.exists() else None
    advisor = Advisor(llm, strict_llm=False)
    patcher = TemplatePatcher(recommender.templates)
    loop = advisor_loop(estate, intent_values, advisor, patcher)
    first = loop.passes[0]
    llm_mode = first.llm_status if llm is not None else "disabled"

    # S5 explain (P9) the findings raised on the estate as harvested.
    bundle = build_bundle(
        estate,
        first.findings,
        advisor.controls,
        patcher,
        loop_status=loop.status,
        loop_reason=loop.reason,
        scope_note=""
        if llm_mode == "ok"
        else "rule floor only; relational (DF-7) and resilience (DF-5) findings need the "
        "LLM advisor and were not evaluated",
    )

    model_version = (
        f"rf-recommender+rf-reconstructor+{GEMINI_MODEL if llm_mode == 'ok' else 'rules-only'}"
    )
    record = RunRecord(
        spec_hash=spec_hash(estate),
        graph_version=_graph_version(),
        model_version=model_version,
        seed=seed,
    )
    prefix = f"runs/{record.run_id[:16]}"
    artifacts = {
        "run_record": store.put(f"{prefix}/run_record.json", _json(record.to_dict())),
        "bundle": store.put(f"{prefix}/bundle.json", bundle_json(bundle)),
        "patched_spec": store.put(
            f"{prefix}/patched_spec.tf.json", _json(loop.estate.to_terraform_json())
        ),
        **{
            f"explanation_{a}": store.put(f"{prefix}/explanation_{a}.md", render(bundle, a))
            for a in AUDIENCES
        },
    }
    if loop.status == "CONTESTED":
        notifier.notify(
            f"KGCR review {loop.status}",
            f"estate {estate.estate_id}: {loop.reason}, "
            f"{len(loop.final_findings)} finding(s) outstanding; bundle at {artifacts['bundle']}",
        )
    return ReviewRun(
        target=target,
        graph_nodes=graph.node_count,
        graph_edges=graph.edge_count,
        intent=intent,
        escalated=escalated,
        recommended=recommended,
        missing_from_estate=tuple(sorted(wanted - observed)),
        unexpected_in_estate=tuple(sorted(observed - wanted)),
        llm_mode=llm_mode,
        loop=loop,
        reviewed_findings=first.findings,
        bundle=bundle,
        record=record,
        artifacts=artifacts,
    )


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
