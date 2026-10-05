"""The bounded advisor loop (FD-02 section 5) and the template patcher.

The loop follows the FD-02 section 5.4 reference implementation rule for rule:
cap of 3 passes (P1), early exit on zero CRITICAL and HIGH (P2), halt on a repeated
spec hash (P3), halt when the CRITICAL count rises (P5), and CONTESTED rather than a
silent pass when the cap is reached with findings outstanding (P6). Waivers (P4)
and the acceptance-gate counter reset (P7) need a user in the loop and are not
modelled here.

The patcher is the recommender in patch mode (FD-01 section 3 patcher note): it
repairs a flagged resource by aligning it, one attribute at a time, with the
recommender's compliant template for that resource type. It cannot remove a
relational edge, because that needs design intent; an unpatchable finding leaves
the spec unchanged and the loop halts as OSCILLATING (P3), which is the correct
FD-02 outcome and is reported as such.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from kgcr.advisor.advisor import PROMPT_VERSION, Advisor, AdvisorFinding, Review
from kgcr.corpus.estate import Estate
from kgcr.corpus.resources import Resource
from kgcr.defects.detectors import resource_findings
from kgcr.defects.taxonomy import Severity
from kgcr.hashing import canonical_hash
from kgcr.recommender.recommender import IDENTITY_ATTRIBUTES

__all__ = ["MAX_PASSES", "LoopResult", "TemplatePatcher", "spec_hash", "advisor_loop"]

MAX_PASSES = 3


def spec_hash(estate: Estate) -> str:
    """Canonical hash of the spec content (FD-02 rule P3)."""
    return canonical_hash([r.to_dict() for r in estate.resources])


@dataclass(frozen=True, slots=True)
class LoopResult:
    """How the loop ended, and every pass it took to get there."""

    status: str  # "CONVERGED" | "CONTESTED"
    reason: str  # "CLEAN" | "OSCILLATING" | "DIVERGING" | "NON_CONVERGENT"
    passes: tuple[Review, ...]
    estate: Estate

    @property
    def final_findings(self) -> tuple[AdvisorFinding, ...]:
        return self.passes[-1].findings


class TemplatePatcher:
    """Repair flagged resources toward a compliant template of the same type."""

    def __init__(self, templates: Mapping[str, Resource]) -> None:
        self.templates = dict(templates)

    def _repair(self, res: Resource) -> Resource:
        template = self.templates.get(res.type)
        if template is None:
            return res
        keys = sorted(
            k
            for k in set(res.attributes) | set(template.attributes)
            if k not in IDENTITY_ATTRIBUTES and not k.startswith("__ref__")
        )

        def aligned(current: Resource, key: str) -> Resource:
            attrs = dict(current.attributes)
            if key in template.attributes:
                attrs[key] = template.attributes[key]
            else:
                attrs.pop(key, None)
            return replace(current, attributes=attrs)

        if resource_findings(res):
            # Greedy: keep a change only if it removes a single-resource finding.
            for key in keys:
                trial = aligned(res, key)
                if len(resource_findings(trial)) < len(resource_findings(res)):
                    res = trial
            return res
        # No rule fires (an LLM-raised finding): align every configurable scalar.
        for key in keys:
            if not isinstance(template.attributes.get(key), dict | list):
                res = aligned(res, key)
        return res

    def patch(self, estate: Estate, findings: tuple[AdvisorFinding, ...]) -> Estate:
        flagged = {a for f in findings for a in f.affected_elements}
        resources = tuple(self._repair(r) if r.address in flagged else r for r in estate.resources)
        return replace(estate, resources=resources)


def advisor_loop(
    estate: Estate,
    intent: Mapping[str, str],
    advisor: Advisor,
    patcher: TemplatePatcher,
    *,
    max_passes: int = MAX_PASSES,
) -> LoopResult:
    """Review, patch, re-review until clean or a halting rule fires."""
    seen = {spec_hash(estate)}
    prev_critical: int | None = None
    passes: list[Review] = []
    prior: tuple[AdvisorFinding, ...] = ()

    for n in range(1, max_passes + 1):
        review = advisor.review(
            estate,
            intent,
            pass_number=n,
            prior=prior,
            label=f"{PROMPT_VERSION}-{estate.estate_id}-loop-p{n}",
        )
        passes.append(review)
        critical = review.count(Severity.CRITICAL)
        if critical == 0 and review.count(Severity.HIGH) == 0:  # P2
            return LoopResult("CONVERGED", "CLEAN", tuple(passes), estate)
        if prev_critical is not None and critical > prev_critical:  # P5
            return LoopResult("CONTESTED", "DIVERGING", tuple(passes), estate)
        prev_critical = critical
        if n == max_passes:  # P6
            return LoopResult("CONTESTED", "NON_CONVERGENT", tuple(passes), estate)
        estate = patcher.patch(estate, review.findings)
        h = spec_hash(estate)
        if h in seen:  # P3
            return LoopResult("CONTESTED", "OSCILLATING", tuple(passes), estate)
        seen.add(h)
        prior = review.findings
    raise AssertionError("unreachable: the n == max_passes branch always returns")
