"""Design mode end to end (FD-01 S1a to S5), run locally.

stated intent -> candidate spec (generator skeleton audited by the recommender) -> advisor
loop -> dependency graph -> explanation -> stored artifacts.

The advisor sees the spec and the stated intent only. Nothing from the recommender (its
scores, its options, its audit) reaches the advisor prompt (INV-7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kgcr.advisor.advisor import Advisor, AdvisorFinding
from kgcr.advisor.llm import GEMINI_MODEL, LLMClient
from kgcr.advisor.loop import LoopResult, TemplatePatcher, advisor_loop, spec_hash
from kgcr.corpus.graph import build_graph_from_estate
from kgcr.corpus.intent import Intent
from kgcr.corpus.pipeline import generate_corpus
from kgcr.corpus.splits import split_estates
from kgcr.defects.pipeline import inject_corpus
from kgcr.design.synthesize import Candidate, intent_values, synthesize
from kgcr.explainer.explainer import AUDIENCES, ExplanationBundle, build_bundle, bundle_json, render
from kgcr.orchestration.aws import ArtifactStore, LocalArtifactStore, Notifier
from kgcr.orchestration.common import StageClock, graph_version, to_json
from kgcr.orchestration.lifecycle import append_event
from kgcr.recommender.recommender import OptionRecommender
from kgcr.reconstruction.reconstructor import RECONSTRUCTED_FIELDS
from kgcr.repro import DEFAULT_SEED, seed_everything
from kgcr.runrecord import RunRecord

__all__ = ["DesignRun", "run_design"]


@dataclass(frozen=True, slots=True)
class DesignRun:
    """Everything one design produced, for printing and for tests."""

    intent: Intent
    candidate: Candidate
    graph_nodes: int
    graph_edges: int
    llm_mode: str
    loop: LoopResult
    reviewed_findings: tuple[AdvisorFinding, ...]
    bundle: ExplanationBundle
    record: RunRecord
    artifacts: dict[str, str]


def run_design(
    *,
    intent: Intent,
    store: ArtifactStore,
    notifier: Notifier,
    llm: LLMClient | None,
    count: int = 180,
    seed: int = DEFAULT_SEED,
) -> DesignRun:
    """Design mode. ``llm`` is injected so callers (and tests) decide whether the advisor
    may reach a model."""
    clock = StageClock()
    seed_everything(seed)
    corpus = generate_corpus(count, seed)
    split = split_estates(corpus)
    by_id = {e.estate_id: e for e in corpus}
    fit = [by_id[i] for i in (*split.train.estate_ids, *split.validation.estate_ids)]
    clock.mark("corpus")

    recommender = OptionRecommender(random_state=0)
    recommender.fit(fit, [d.estate for d in inject_corpus(fit)])
    candidate = synthesize(intent, seed, recommender)
    estate = candidate.estate
    clock.mark("synthesize")

    graph = build_graph_from_estate(estate)
    clock.mark("graph")

    stated = intent_values(intent)
    advisor = Advisor(llm, strict_llm=False)
    patcher = TemplatePatcher(recommender.templates)
    loop = advisor_loop(estate, stated, advisor, patcher)
    first = loop.passes[0]
    statuses = [p.llm_status for p in loop.passes]
    llm_mode = "disabled" if llm is None else "ok" if set(statuses) == {"ok"} else "partial"
    if llm_mode == "partial" and statuses[0] != "ok":
        llm_mode = statuses[0]
    clock.mark("advise")

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
    model_version = f"rf-recommender+{GEMINI_MODEL if llm_mode == 'ok' else 'rules-only'}"
    record = RunRecord(
        spec_hash=spec_hash(estate),
        graph_version=graph_version(),
        model_version=model_version,
        seed=seed,
    )
    clock.mark("explain")

    summary: dict[str, Any] = {
        "mode": "design",
        "estate_id": estate.estate_id,
        "variant": None,
        "defect_class": None,
        "severity": None,
        "detectability": None,
        "llm_mode": llm_mode,
        "graph": {
            "nodes": [{"address": n.address, "type": n.type} for n in graph.nodes],
            "edges": [[e.source, e.target] for e in graph.edges],
        },
        # Stated by the operator, not reconstructed: no confidence to report.
        "intent": {
            "source": "stated",
            "region": intent.region,
            "fields": {f: {"value": stated[f], "confidence": None} for f in RECONSTRUCTED_FIELDS},
        },
        "escalated": [],
        "escalation_threshold": None,
        "recommended": [
            {"option": list(r.option), "score": r.score} for r in candidate.recommended
        ],
        "missing_from_estate": [list(o) for o in candidate.reported_missing],
        "unexpected_in_estate": [list(o) for o in candidate.reported_unexpected],
        "design": {
            "applied": [list(o) for o in candidate.applied],
            "reported_missing": [list(o) for o in candidate.reported_missing],
            "reported_unexpected": [list(o) for o in candidate.reported_unexpected],
        },
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
        "summary": store.put(f"{prefix}/summary.json", to_json(summary)),
        "timings": store.put(f"{prefix}/timings.json", to_json(clock.stages)),
        "run_record": store.put(f"{prefix}/run_record.json", to_json(record.to_dict())),
        "bundle": store.put(f"{prefix}/bundle.json", bundle_json(bundle)),
        "patched_spec": store.put(
            f"{prefix}/patched_spec.tf.json", to_json(loop.estate.to_terraform_json())
        ),
        **{
            f"explanation_{a}": store.put(f"{prefix}/explanation_{a}.md", render(bundle, a))
            for a in AUDIENCES
        },
    }
    if isinstance(store, LocalArtifactStore):
        append_event(Path(store.root), record.run_id[:16], "designed", estate_id=estate.estate_id)
    if loop.status == "CONTESTED":
        notifier.notify(
            f"KGCR design {loop.status}",
            f"estate {estate.estate_id}: {loop.reason}, "
            f"{len(loop.final_findings)} finding(s) outstanding; bundle at {artifacts['bundle']}",
        )
    return DesignRun(
        intent=intent,
        candidate=candidate,
        graph_nodes=graph.node_count,
        graph_edges=graph.edge_count,
        llm_mode=llm_mode,
        loop=loop,
        reviewed_findings=first.findings,
        bundle=bundle,
        record=record,
        artifacts=artifacts,
    )
