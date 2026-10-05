"""The Explainer (FD-06), template-first: bundle, counterfactuals, three renderings.

Every finding the advisor raises is symbolic, so its justification is the *exact*
evidence it carries (FD-06 section 5): the affected elements and, for relational
findings, the evidence path. No learned extraction is needed.

Counterfactuals come from constrained re-evaluation (FD-06 section 6), never from a
model: perturb the spec with one coherent change, re-run the same checks, report
what actually happens.

* single-resource finding: repair the element toward its compliant template and
  re-run the rules;
* relational finding: cut the reference between the last hop and the sink, then
  re-run the bounded traversal. If another path survives, that is reported.

Cost deltas are part of FD-06's "consequence" component but need L1 cost facts,
which do not exist yet; the bundle says so rather than inventing a number.

Renderings are plain templates (no LLM): ``architect``, ``auditor``, ``learner``.
INV-2 is checked by :func:`extract_claims`, which pulls control references,
severities, resource addresses and counterfactual outcomes back *out of the
rendered text*. All three audiences must yield the same claim set.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from kgcr.advisor.advisor import AdvisorFinding
from kgcr.advisor.controls import Control
from kgcr.advisor.loop import TemplatePatcher
from kgcr.corpus.estate import Estate
from kgcr.defects.detectors import relational_path_exists, resource_findings
from kgcr.defects.taxonomy import Severity

__all__ = [
    "AUDIENCES",
    "MAX_COUNTERFACTUALS",
    "Counterfactual",
    "ExplainedFinding",
    "ExplanationBundle",
    "build_bundle",
    "render",
    "extract_claims",
]

AUDIENCES: tuple[str, ...] = ("architect", "auditor", "learner")
MAX_COUNTERFACTUALS = 3
COST_NOTE = "cost delta not modelled: L1 carries no cost facts yet"

_SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}


@dataclass(frozen=True, slots=True)
class Counterfactual:
    """One evaluated perturbation and its outcome."""

    change: str
    resolved: bool
    detail: str

    @property
    def outcome(self) -> str:
        return "RESOLVED" if self.resolved else "NOT RESOLVED"


@dataclass(frozen=True, slots=True)
class ExplainedFinding:
    """Justification, provenance, consequence and (optionally) a counterfactual."""

    control_ref: str
    control_summary: str
    control_verified: bool
    severity: Severity
    affected_elements: tuple[str, ...]
    evidence_path: tuple[str, ...]
    assertion: str
    counterfactual: Counterfactual | None


@dataclass(frozen=True, slots=True)
class ExplanationBundle:
    """Everything any rendering may say. Renderings add no facts (INV-2)."""

    estate_id: str
    loop_status: str
    loop_reason: str
    findings: tuple[ExplainedFinding, ...]
    cost_note: str = COST_NOTE
    scope_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "estate_id": self.estate_id,
            "loop_status": self.loop_status,
            "loop_reason": self.loop_reason,
            "cost_note": self.cost_note,
            "scope_note": self.scope_note,
            "findings": [
                {
                    "control_ref": f.control_ref,
                    "control_summary": f.control_summary,
                    "control_verified": f.control_verified,
                    "severity": f.severity.value,
                    "affected_elements": list(f.affected_elements),
                    "evidence_path": list(f.evidence_path),
                    "assertion": f.assertion,
                    "counterfactual": None
                    if f.counterfactual is None
                    else {
                        "change": f.counterfactual.change,
                        "outcome": f.counterfactual.outcome,
                        "detail": f.counterfactual.detail,
                    },
                }
                for f in self.findings
            ],
        }


def _counterfactual(
    estate: Estate, finding: AdvisorFinding, patcher: TemplatePatcher
) -> Counterfactual:
    if len(finding.evidence_path) >= 2:
        source, sink = finding.evidence_path[0], finding.evidence_path[-1]
        hop = finding.evidence_path[-2]
        cut = tuple(
            replace(r, references=tuple(x for x in r.references if x != sink))
            if r.address == hop
            else replace(r, references=tuple(x for x in r.references if x != hop))
            if r.address == sink
            else r
            for r in estate.resources
        )
        survivor = relational_path_exists(replace(estate, resources=cut), source, sink)
        return Counterfactual(
            f"remove the reference between {hop} and {sink}",
            survivor is None,
            "no path remains within 3 hops"
            if survivor is None
            else f"another path remains: {' -> '.join(survivor)}",
        )
    by_address = {r.address: r for r in estate.resources}
    before = [by_address[a] for a in finding.affected_elements]
    after = patcher.patch(estate, (finding,))
    after_by_address = {r.address: r for r in after.resources}
    remaining = [
        f for a in finding.affected_elements for f in resource_findings(after_by_address[a])
    ]
    if not any(resource_findings(r) for r in before):
        return Counterfactual(
            f"align {', '.join(finding.affected_elements)} with the compliant template",
            False,
            "no single-resource rule backs this finding; re-evaluation needs the advisor model",
        )
    return Counterfactual(
        f"align {', '.join(finding.affected_elements)} with the compliant template",
        not remaining,
        "single-resource rules pass after the change"
        if not remaining
        else f"still failing: {', '.join(f.rule_id for f in remaining)}",
    )


def build_bundle(
    estate: Estate,
    findings: Sequence[AdvisorFinding],
    controls: Mapping[str, Control],
    patcher: TemplatePatcher,
    *,
    loop_status: str,
    loop_reason: str,
    scope_note: str = "",
) -> ExplanationBundle:
    """Explain ``findings`` on ``estate``; counterfactuals for the top three by severity."""
    ordered = sorted(findings, key=lambda f: (_SEVERITY_ORDER[f.severity], f.key))
    explained: list[ExplainedFinding] = []
    for i, f in enumerate(ordered):
        control = controls[f.control_node]
        explained.append(
            ExplainedFinding(
                control.control_ref,
                control.summary,
                control.verified,
                f.severity,
                f.affected_elements,
                f.evidence_path,
                f.assertion,
                _counterfactual(estate, f, patcher) if i < MAX_COUNTERFACTUALS else None,
            )
        )
    return ExplanationBundle(
        estate.estate_id, loop_status, loop_reason, tuple(explained), scope_note=scope_note
    )


_ACRONYMS = {
    "PCI-DSS": "Payment Card Industry Data Security Standard",
    "CIS-AWS": "Center for Internet Security benchmark for Amazon Web Services",
    "AWS-WAR": "Amazon Web Services Well-Architected review",
}


def _expand(ref: str) -> str:
    for short, long in _ACRONYMS.items():
        if ref.startswith(short):
            return f"{ref} [{long}]"
    return ref


def _path(f: ExplainedFinding) -> str:
    return " -> ".join(f.evidence_path)


def _render_finding(f: ExplainedFinding, audience: str, n: int) -> list[str]:
    elements = ", ".join(f.affected_elements)
    cf = f.counterfactual
    draft = "" if f.control_verified else " (control text is a draft pending review)"
    if audience == "architect":
        lines = [f"{n}. [{f.severity.value}] {elements}: {f.assertion}"]
        if f.evidence_path:
            lines.append(f"   path: {_path(f)}")
        lines.append(f"   control: {f.control_ref}{draft}")
        if cf:
            lines.append(f"   if you {cf.change}: {cf.outcome} ({cf.detail})")
    elif audience == "auditor":
        lines = [
            f"{n}. Control {f.control_ref}{draft}: {f.control_summary}",
            f"   Severity {f.severity.value}. Not met by: {elements}.",
            f"   Finding: {f.assertion}",
        ]
        if f.evidence_path:
            lines.append(f"   Evidence trail: {_path(f)}")
        if cf:
            lines.append(f"   Remediation tested: {cf.change}. Outcome: {cf.outcome}; {cf.detail}.")
    else:
        kind = "relational" if f.evidence_path else "single-resource"
        lines = [
            f"{n}. A {kind} finding with severity {f.severity.value}, under "
            f"{_expand(f.control_ref)}{draft}.",
            f"   The rule in plain words: {f.control_summary}",
            f"   What is affected: {elements}. Why it is flagged: {f.assertion}",
        ]
        if f.evidence_path:
            lines.append(
                "   No single setting is wrong on its own here; the problem is the chain "
                f"of connections {_path(f)}."
            )
        if cf:
            lines.append(
                f"   We tested a fix ({cf.change}) and the result was: {cf.outcome}. "
                f"In detail: {cf.detail}."
            )
    return lines


def render(bundle: ExplanationBundle, audience: str) -> str:
    """Render ``bundle`` for one audience. Wording changes; claims do not."""
    if audience not in AUDIENCES:
        raise ValueError(f"unknown audience {audience!r}; expected one of {AUDIENCES}")
    titles = {
        "architect": f"Review of {bundle.estate_id}",
        "auditor": f"Compliance review, estate {bundle.estate_id}",
        "learner": f"What the review found in estate {bundle.estate_id}, explained",
    }
    lines = [
        titles[audience],
        f"Loop outcome: {bundle.loop_status} ({bundle.loop_reason}).",
        f"Note: {bundle.cost_note}.",
    ]
    if bundle.scope_note:
        lines.append(f"Scope: {bundle.scope_note}.")
    lines.append("")
    if not bundle.findings:
        lines.append("No findings.")
    for n, f in enumerate(bundle.findings, start=1):
        lines.extend(_render_finding(f, audience, n))
    return "\n".join(lines) + "\n"


_CLAIM_PATTERNS = (
    re.compile(r"\b(?:PCI-DSS|CIS-AWS|AWS-WAR)-[\w.\-]*\w"),
    re.compile(r"\b(?:CRITICAL|HIGH|MEDIUM|ADVISORY)\b"),
    re.compile(r"\baws_\w+\.\w+"),
    re.compile(r"\bNOT RESOLVED\b|(?<!NOT )\bRESOLVED\b"),
    re.compile(r"\b(?:CONVERGED|CONTESTED)\b"),
)


def extract_claims(text: str) -> frozenset[str]:
    """The checkable claims in a rendering: controls, severities, resources, outcomes."""
    claims: set[str] = set()
    for pattern in _CLAIM_PATTERNS:
        claims.update(m.group(0).strip() for m in pattern.finditer(text))
    return frozenset(claims)


def bundle_json(bundle: ExplanationBundle) -> str:
    return json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
