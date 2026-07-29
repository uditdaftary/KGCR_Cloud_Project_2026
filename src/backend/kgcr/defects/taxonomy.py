"""The defect taxonomy (FD-05 §5) and the per-defect ground-truth record.

Defect classes are ``DF-1``…``DF-7``, kept in their own namespace so they never
collide with the decision-register ``D1``…``D17`` IDs. Each class carries the
control it typically breaches (an FD-07 ``kg://`` URI) and a severity.

Severity is duplicated here for convenience, but the *authoritative* value lives
on the L1 ``Control`` node the ``control`` URI resolves to (FD-07 §6): severity
is a property of the control, not of the detection mechanism. Until Phase 1
lands that node, the mapping below is the stand-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "DefectClass",
    "Severity",
    "Detectability",
    "DefectInstance",
    "DEFAULT_CONTROL",
    "DEFAULT_SEVERITY",
    "DETECTABILITY",
]


class DefectClass(StrEnum):
    """The seven defect classes of FD-05 §5, valued by their ``DF-n`` code."""

    EXPOSURE = "DF-1"
    ENCRYPTION = "DF-2"
    IDENTITY = "DF-3"
    OBSERVABILITY = "DF-4"
    RESILIENCE = "DF-5"
    COST = "DF-6"
    RELATIONAL = "DF-7"


class Severity(StrEnum):
    """Severity band (FD-07 §6). Derived from the control, not the detector."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    ADVISORY = "ADVISORY"


class Detectability(StrEnum):
    """Whether a single-resource policy engine can reach the defect (FD-05 §5)."""

    FULL = "yes"
    PARTIAL = "partly"
    NONE = "no"


# Default control breached, per class, as an FD-07 §4.3 ``kg://`` URI. Injectors
# may override with a more specific clause per variant. These resolve to L1
# Control nodes once Phase 1 is encoded; today they are citable strings.
DEFAULT_CONTROL: dict[DefectClass, str] = {
    DefectClass.EXPOSURE: "kg://control/pci-dss-v4/1.3",
    DefectClass.ENCRYPTION: "kg://control/pci-dss-v4/3.4",
    DefectClass.IDENTITY: "kg://control/pci-dss-v4/7.2",
    DefectClass.OBSERVABILITY: "kg://control/cis-aws/3.2",
    DefectClass.RESILIENCE: "kg://control/aws-war/reliability-multi-az",
    DefectClass.COST: "kg://control/aws-war/cost-rightsizing",
    DefectClass.RELATIONAL: "kg://control/pci-dss-v4/1.3",
}

# ponytail: severity is mirrored from the control here; the single source of
# truth is the L1 Control node (FD-07 §6). Resolve against it once P1 lands and
# drop this table. Values follow the FD-07 §6 derivation (mandatory→CRITICAL,
# hardening→HIGH, heuristic→MEDIUM).
DEFAULT_SEVERITY: dict[DefectClass, Severity] = {
    DefectClass.EXPOSURE: Severity.CRITICAL,
    DefectClass.ENCRYPTION: Severity.CRITICAL,
    DefectClass.IDENTITY: Severity.CRITICAL,
    DefectClass.OBSERVABILITY: Severity.HIGH,
    DefectClass.RESILIENCE: Severity.MEDIUM,
    DefectClass.COST: Severity.MEDIUM,
    DefectClass.RELATIONAL: Severity.CRITICAL,
}

DETECTABILITY: dict[DefectClass, Detectability] = {
    DefectClass.EXPOSURE: Detectability.FULL,
    DefectClass.ENCRYPTION: Detectability.FULL,
    DefectClass.IDENTITY: Detectability.FULL,
    DefectClass.OBSERVABILITY: Detectability.FULL,
    DefectClass.RESILIENCE: Detectability.PARTIAL,
    DefectClass.COST: Detectability.PARTIAL,
    DefectClass.RELATIONAL: Detectability.NONE,
}


@dataclass(frozen=True, slots=True)
class DefectInstance:
    """Ground truth for one injected defect (FD-05 §5).

    Records everything the seeded-recall metric (FD-04 §10) needs to score a
    detector: what was injected, where, which control it breaches, and — for
    relational (DF-7) defects — the ``evidence_path`` a graph traversal must
    recover. ``estate_id`` is the injected estate's own id; ``parent_estate_id``
    and ``seed_family`` tie it to the clean estate it derives from so the
    estate-level split (FD-05 §9) keeps parent and child together.
    """

    defect_class: DefectClass
    variant: str
    estate_id: str
    parent_estate_id: str
    seed_family: str
    control: str
    severity: Severity
    injection_site: tuple[str, ...]
    expected_finding: str
    # Empty for single-resource defects; the resource chain (source → sink) for
    # relational defects. ``hop_count`` is ``len(evidence_path) - 1``.
    evidence_path: tuple[str, ...] = ()

    @property
    def hop_count(self) -> int:
        return max(len(self.evidence_path) - 1, 0)

    @property
    def is_relational(self) -> bool:
        return self.defect_class is DefectClass.RELATIONAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_class": self.defect_class.value,
            "variant": self.variant,
            "estate_id": self.estate_id,
            "parent_estate_id": self.parent_estate_id,
            "seed_family": self.seed_family,
            "control": self.control,
            "severity": self.severity.value,
            "detectability": DETECTABILITY[self.defect_class].value,
            "injection_site": list(self.injection_site),
            "expected_finding": self.expected_finding,
            "evidence_path": list(self.evidence_path),
            "hop_count": self.hop_count,
        }
