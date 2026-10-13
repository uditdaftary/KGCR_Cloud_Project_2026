"""The automated half of FD-06 section 9: faithfulness and cross-audience invariance.

What each number is, and is not:

* **Cross-audience invariance** (9.2) is the share of bundles whose three renderings yield the
  same claim set. It is the empirical form of INV-2.
* **Counterfactual validity** (9.1) is measured against an observed outcome, not recomputed with
  the code that produced it. A single-resource counterfactual says "align this resource with
  its compliant template: RESOLVED". The advisor loop actually applies that repair and reviews
  again; validity is the share where the prediction matches what the loop then found. Relational
  counterfactuals are counted but cannot be checked this way here.
* **Sparsity** is evidence size over graph size, reported as measured.
* **Fidelity+ and Fidelity-** are defined for relational findings, where they are non-trivial:
  remove the evidence path and the path must be gone; keep only the evidence path and it must
  remain. For a single-resource finding the evidence is the resource itself, so both hold by
  construction and are not reported as measurements.
* **Verbalisation fidelity** does not apply: explanations are templates, not language-model text.

Samples are small; every figure is reported with its n.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from statistics import mean, median
from typing import Any

from kgcr.advisor.advisor import AdvisorFinding
from kgcr.advisor.loop import LoopResult
from kgcr.corpus.estate import Estate
from kgcr.corpus.graph import build_graph_from_estate
from kgcr.defects.detectors import relational_path_exists
from kgcr.explainer.explainer import (
    AUDIENCES,
    ExplanationBundle,
    extract_claims,
    render,
)

__all__ = ["EvalCase", "evaluate_cases"]


@dataclass(frozen=True, slots=True)
class EvalCase:
    name: str
    estate: Estate
    bundle: ExplanationBundle
    first_pass: tuple[AdvisorFinding, ...]
    loop: LoopResult


def _invariant(bundle: ExplanationBundle) -> bool:
    claims = [extract_claims(render(bundle, a)) for a in AUDIENCES]
    return all(c == claims[0] for c in claims)


def _counterfactual_agreement(case: EvalCase) -> list[bool]:
    """For each single-resource counterfactual: did the loop's own repair agree with it?"""
    final = {
        (f.affected_elements, f.assertion) for f in case.loop.final_findings
    }
    outcomes: list[bool] = []
    for f in case.bundle.findings:
        cf = f.counterfactual
        if cf is None or f.evidence_path:
            continue
        # Only where the loop repaired this resource: otherwise nothing was observed.
        if len(case.loop.passes) < 2:
            continue
        still_there = (f.affected_elements, f.assertion) in final
        outcomes.append(cf.resolved == (not still_there))
    return outcomes


def _fidelity(case: EvalCase) -> tuple[list[bool], list[bool]]:
    """(Fidelity+, Fidelity-) for each relational finding with a path."""
    plus: list[bool] = []
    minus: list[bool] = []
    for f in case.bundle.findings:
        path = f.evidence_path
        if len(path) < 2:
            continue
        source, sink = path[0], path[-1]
        keep = set(path)
        without = replace(
            case.estate, resources=tuple(r for r in case.estate.resources if r.address not in keep)
        )
        only = replace(
            case.estate, resources=tuple(r for r in case.estate.resources if r.address in keep)
        )
        plus.append(relational_path_exists(without, source, sink) is None)
        minus.append(relational_path_exists(only, source, sink) is not None)
    return plus, minus


def _rate(values: Sequence[bool]) -> dict[str, Any]:
    return {"n": len(values), "rate": round(sum(values) / len(values), 3) if values else None}


def evaluate_cases(cases: Sequence[EvalCase]) -> dict[str, Any]:
    sparsity: list[float] = []
    agreement: list[bool] = []
    plus: list[bool] = []
    minus: list[bool] = []
    relational = single = with_counterfactual = 0
    for case in cases:
        nodes = build_graph_from_estate(case.estate).node_count
        for f in case.bundle.findings:
            size = len(f.evidence_path or f.affected_elements)
            sparsity.append(size / nodes)
            relational += int(bool(f.evidence_path))
            single += int(not f.evidence_path)
            with_counterfactual += int(f.counterfactual is not None)
        agreement += _counterfactual_agreement(case)
        p, m = _fidelity(case)
        plus += p
        minus += m
    return {
        "bundles": len(cases),
        "findings": {
            "single_resource": single,
            "relational": relational,
            "with_a_counterfactual": with_counterfactual,
        },
        "cross_audience_invariance": _rate([_invariant(c.bundle) for c in cases]),
        "counterfactual_validity": {
            **_rate(agreement),
            "measured_against": "the outcome the advisor loop observed after applying the repair",
            "not_checked": "relational counterfactuals (the loop cannot apply them)",
        },
        "sparsity": {
            "n": len(sparsity),
            "mean": round(mean(sparsity), 3) if sparsity else None,
            "median": round(median(sparsity), 3) if sparsity else None,
            "max": round(max(sparsity), 3) if sparsity else None,
            "definition": "evidence elements over resources in the estate",
        },
        "fidelity_plus": {**_rate(plus), "scope": "relational findings only"},
        "fidelity_minus": {**_rate(minus), "scope": "relational findings only"},
        "verbalisation_fidelity": "not applicable: explanations are templates, not model text",
    }
