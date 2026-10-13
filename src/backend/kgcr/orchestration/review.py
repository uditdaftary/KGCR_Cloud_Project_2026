"""Review mode end to end (FD-01 S1b to S5), run locally.

estate -> graph -> reconstructed intent (P8) -> recommended options (P7) ->
advisor loop (P6) -> explanation (P9) -> stored artifacts.

The estate is *harvested* from the synthetic corpus, standing in for AWS Config:
the target is drawn from the held-out test split and defect-injected, so neither
the reconstructor nor the recommender has seen it. Both models are fitted on the
train+validation split only, in seconds and deterministically, so nothing is
unpickled.

Besides the bundle, each run stores ``summary.json`` (the estate graph, intent,
recommendation and loop passes, deterministic) and ``timings.json`` (wall-clock
seconds per stage, informational) for the dashboard to draw.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from kgcr.advisor.advisor import Advisor, AdvisorFinding
from kgcr.advisor.controls import DRAFT_CONTROLS_PATH
from kgcr.advisor.llm import GEMINI_MODEL, LLMClient, default_llm
from kgcr.advisor.loop import LoopResult, TemplatePatcher, advisor_loop, spec_hash
from kgcr.corpus.estate import Estate
from kgcr.corpus.graph import build_graph_from_estate
from kgcr.corpus.pipeline import generate_corpus
from kgcr.corpus.splits import split_estates
from kgcr.defects.inject import DefectedEstate, applicable_injectors
from kgcr.defects.pipeline import inject_corpus
from kgcr.defects.taxonomy import DEFAULT_SEVERITY, DETECTABILITY
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
from kgcr.repro import DEFAULT_SEED, seed_everything
from kgcr.runrecord import RunRecord

__all__ = ["ReviewRun", "select_target", "default_llm", "run_review"]


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
    llm: LLMClient | None,
    count: int = 180,
    seed: int = DEFAULT_SEED,
) -> ReviewRun:
    """Run review mode. ``llm`` is injected so callers (and tests) decide whether
    the advisor may reach a model; :func:`default_llm` is what the CLI passes."""
    clock = _StageClock()
    seed_everything(seed)
    corpus = generate_corpus(count, seed)
    split = split_estates(corpus)
    by_id = {e.estate_id: e for e in corpus}
    fit = [by_id[i] for i in (*split.train.estate_ids, *split.validation.estate_ids)]
    target = select_target([by_id[i] for i in split.test.estate_ids], variant)
    estate = target.estate
    clock.mark("harvest")

    # S1b harvest is the corpus stand-in above; S1c reconstruct intent (P8).
    graph = build_graph_from_estate(estate)
    clock.mark("graph")
    reconstructor = IntentReconstructor(random_state=0)
    reconstructor.fit(fit)
    intent = reconstructor.reconstruct(estate)
    escalated = tuple(sorted(intent.low_confidence_fields(ESCALATION_THRESHOLD)))
    intent_values = intent_from_reconstruction(intent)
    clock.mark("intent")

    # S2 recommend (P7): what this intent should look like, versus what is there.
    recommender = OptionRecommender(random_state=0)
    recommender.fit(fit, [d.estate for d in inject_corpus(fit)])
    recommended = tuple(recommender.recommend(intent_values))
    wanted = {r.option for r in recommended if r.score >= 0.5}
    observed = estate_options(estate)
    clock.mark("recommend")

    # S3 advisor loop (P6). Gemini replays fixtures; without one the advisor
    # logs a warning and runs the rule floor only (strict_llm=False).
    advisor = Advisor(llm, strict_llm=False)
    patcher = TemplatePatcher(recommender.templates)
    loop = advisor_loop(estate, intent_values, advisor, patcher)
    first = loop.passes[0]
    # "ok" only if the model answered on every pass; a later pass that fell back to
    # the rule floor (no fixture for that label) must not be reported as LLM-reviewed.
    statuses = [p.llm_status for p in loop.passes]
    llm_mode = "disabled" if llm is None else "ok" if set(statuses) == {"ok"} else "partial"
    if llm_mode == "partial" and statuses[0] != "ok":
        llm_mode = statuses[0]
    clock.mark("advise")

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
        else "rule floor only on at least one pass; relational (DF-7) and resilience (DF-5) "
        "findings need the LLM advisor and were not evaluated on every pass",
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
    clock.mark("explain")
    missing = tuple(sorted(wanted - observed))
    unexpected = tuple(sorted(observed - wanted))
    summary = {
        "estate_id": estate.estate_id,
        "variant": variant,
        "defect_class": target.defect.defect_class.value,
        "severity": DEFAULT_SEVERITY[target.defect.defect_class].value,
        "detectability": DETECTABILITY[target.defect.defect_class].value,
        "llm_mode": llm_mode,
        "graph": {
            "nodes": [{"address": n.address, "type": n.type} for n in graph.nodes],
            "edges": [[e.source, e.target] for e in graph.edges],
        },
        "intent": intent.to_dict(),
        "escalated": list(escalated),
        "escalation_threshold": ESCALATION_THRESHOLD,
        "recommended": [{"option": list(r.option), "score": r.score} for r in recommended],
        "missing_from_estate": [list(o) for o in missing],
        "unexpected_in_estate": [list(o) for o in unexpected],
        "loop": {
            "status": loop.status,
            "reason": loop.reason,
            "passes": [
                {
                    "llm_status": p.llm_status,
                    "llm_proposed": p.llm_proposed,
                    "llm_admitted": len(p.llm_admitted),
                    "findings": [
                        {
                            "control_node": f.control_node,
                            "severity": f.severity.value,
                            "affected_elements": list(f.affected_elements),
                            "origin": f.origin,
                        }
                        for f in p.findings
                    ],
                }
                for p in loop.passes
            ],
        },
    }
    prefix = f"runs/{record.run_id[:16]}"
    artifacts = {
        "summary": store.put(f"{prefix}/summary.json", _json(summary)),
        "timings": store.put(f"{prefix}/timings.json", _json(clock.stages)),
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
        missing_from_estate=missing,
        unexpected_in_estate=unexpected,
        llm_mode=llm_mode,
        loop=loop,
        reviewed_findings=first.findings,
        bundle=bundle,
        record=record,
        artifacts=artifacts,
    )


class _StageClock:
    """Wall-clock seconds per pipeline stage, measured between successive marks."""

    def __init__(self) -> None:
        self._last = time.perf_counter()
        self.stages: list[dict[str, Any]] = []

    def mark(self, stage: str) -> None:
        now = time.perf_counter()
        self.stages.append({"stage": stage, "seconds": round(now - self._last, 4)})
        self._last = now


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
