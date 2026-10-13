"""Per-choice justification for a designed spec (D1; FD-06 sections 3 and 6).

A review explains findings. A design has none to explain, so each choice is justified by
what its rejected alternatives would violate. The alternatives come from the options the
recommender retrieved for the same resource type and attribute, and the findings from
re-evaluating each one in a compliant context (``option_findings``): computed, not
narrated, so the justification is exact.

Only choices the controls actually constrain are narrated. The rest are counted.
"""

from __future__ import annotations

from collections.abc import Mapping

from kgcr.advisor.controls import Control
from kgcr.corpus.estate import Estate
from kgcr.defects.taxonomy import DEFAULT_CONTROL, DEFAULT_SEVERITY, Severity
from kgcr.explainer.explainer import Alternative, Justification
from kgcr.recommender.recommender import OptionRecommender, resource_options

__all__ = ["build_justifications"]

_SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}


def build_justifications(
    estate: Estate, recommender: OptionRecommender, controls: Mapping[str, Control]
) -> tuple[tuple[Justification, ...], int]:
    """The constrained choices in ``estate`` and the count of unconstrained ones."""
    by_slot: dict[tuple[str, str], list[str]] = {}
    for res_type, attribute, value in recommender.candidates:
        by_slot.setdefault((res_type, attribute), []).append(value)

    justifications: list[Justification] = []
    unconstrained = 0
    for res in estate.resources:
        for (res_type, attribute, chosen), _ in resource_options(res):
            if attribute == "present":
                continue
            alternatives: list[Alternative] = []
            for value in sorted(by_slot.get((res_type, attribute), [])):
                if value == chosen:
                    continue
                for finding in recommender.option_findings((res_type, attribute, value)):
                    control = controls[DEFAULT_CONTROL[finding.defect_class]]
                    alternatives.append(
                        Alternative(
                            value=value,
                            control_ref=control.control_ref,
                            control_verified=control.verified,
                            severity=DEFAULT_SEVERITY[finding.defect_class],
                            rule_id=finding.rule_id,
                        )
                    )
            if not alternatives:
                unconstrained += 1
                continue
            alternatives.sort(key=lambda a: (_SEVERITY_ORDER[a.severity], a.value, a.rule_id))
            justifications.append(
                Justification(res.address, attribute, chosen, tuple(alternatives))
            )
    justifications.sort(
        key=lambda j: (_SEVERITY_ORDER[j.alternatives[0].severity], j.element, j.attribute)
    )
    return tuple(justifications), unconstrained
