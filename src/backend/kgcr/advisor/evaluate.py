"""The P6 evaluation (FD-04 section 10): what runs without a key, and what needs one.

* **Rule floor** — seeded-defect recall per class over the whole defect corpus, and
  CRITICAL false positives over the clean corpus. Deterministic; always runs.
* **LLM** — only with a client (recorded fixtures, or live with opt-in). Relational
  and resilience recall on the sycophancy specs' first pass, CRITICAL false
  positives on a few clean estates, grounding rate, and the sycophancy trials.
  The clean corpus stands in for the gold set because P2 is not started.

Without a client the LLM section reads ``NOT_RUN``; nothing is estimated.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kgcr.advisor.advisor import PROMPT_VERSION, Advisor, AdvisorFinding
from kgcr.advisor.llm import LLMClient
from kgcr.advisor.sycophancy import TARGET_VARIANTS, gate_verdict, run_trial
from kgcr.corpus.estate import Estate
from kgcr.defects.inject import DefectedEstate
from kgcr.defects.pipeline import inject_corpus
from kgcr.defects.taxonomy import DefectInstance, Severity

__all__ = ["N_CLEAN_LLM", "located", "run_advisor_evaluation", "write_report"]

# Clean estates spent on the LLM false-positive check (call budget, see llm.py).
N_CLEAN_LLM = 4


def located(defect: DefectInstance, findings: Sequence[AdvisorFinding]) -> bool:
    """A finding touches the injection site (by affected element or evidence path)."""
    site = set(defect.injection_site)
    return any(site & {*f.affected_elements, *f.evidence_path} for f in findings)


def _first_per_variant(defected: Sequence[DefectedEstate]) -> list[DefectedEstate]:
    chosen: dict[str, DefectedEstate] = {}
    for d in sorted(defected, key=lambda d: d.estate.estate_id):
        chosen.setdefault(d.defect.variant, d)
    return [chosen[v] for v in TARGET_VARIANTS if v in chosen]


def run_advisor_evaluation(estates: Sequence[Estate], llm: LLMClient | None) -> dict[str, Any]:
    """Evaluate the rule floor always, and the LLM path when a client is given."""
    rule_advisor = Advisor(llm=None)
    defected = inject_corpus(estates)

    per_class: dict[str, list[bool]] = defaultdict(list)
    for d in defected:
        findings = rule_advisor.review(d.estate, d.estate.intent.to_dict()).findings
        per_class[d.defect.defect_class.value].append(located(d.defect, findings))
    clean_critical = sum(
        rule_advisor.review(e, e.intent.to_dict()).count(Severity.CRITICAL) for e in estates
    )
    report: dict[str, Any] = {
        "corpus": "synthetic, self-generated (kgcr.corpus + kgcr.defects)",
        "controls_unverified": sum(not c.verified for c in rule_advisor.controls.values()),
        "rule_floor": {
            "note": (
                "Sanity floor, not a benchmark: the injectors produce exactly the "
                "property violations these rules check, so DF-1 to DF-4 recall is "
                "1.0 by construction. DF-5 to DF-7 are outside the rules."
            ),
            "seeded_recall": {
                cls: {"n": len(hits), "recall": round(sum(hits) / len(hits), 4)}
                for cls, hits in sorted(per_class.items())
            },
            "clean_estates": len(estates),
            "clean_critical_findings": clean_critical,
        },
    }
    if llm is None:
        report["llm"] = "NOT_RUN"
        report["sycophancy_gate"] = "NOT_RUN"
        return report

    advisor = Advisor(llm=llm)
    targets = _first_per_variant(defected)
    trials = [
        run_trial(advisor, d.estate, d.estate.intent.to_dict(), d.defect.variant) for d in targets
    ]
    recall = {
        t.variant: located(d.defect, t.passes[0].llm_admitted)
        for t, d in zip(trials, targets, strict=True)
    }
    clean_reviews = [
        advisor.review(e, e.intent.to_dict(), label=f"{PROMPT_VERSION}-clean-{e.estate_id}")
        for e in sorted(estates, key=lambda e: e.estate_id)[:N_CLEAN_LLM]
    ]
    first_passes = [t.passes[0] for t in trials] + clean_reviews
    proposed = sum(r.llm_proposed for r in first_passes)
    admitted = sum(len(r.llm_admitted) for r in first_passes)
    report["llm"] = {
        "model_calls": len(trials) * 3 + len(clean_reviews),
        "seeded_recall_beyond_rule_floor": recall,
        "clean_estates": len(clean_reviews),
        "clean_critical_findings": sum(
            sum(f.severity is Severity.CRITICAL for f in r.llm_admitted) for r in clean_reviews
        ),
        "grounding_rate": None if proposed == 0 else round(admitted / proposed, 4),
        "proposed": proposed,
        "admitted": admitted,
    }
    report["sycophancy_gate"] = gate_verdict(trials)
    report["sycophancy_trials"] = [t.to_dict() for t in trials]
    return report


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
