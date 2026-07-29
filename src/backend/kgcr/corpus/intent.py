"""The intent space — sampled first, rendered into an estate second.

An :class:`Intent` is the ground truth for one synthetic estate: the archetype
it serves plus a choice on each parameter axis of FD-05 §4A. It is frozen and
canonically hashable, so ``intent_hash`` is a stable identity that survives the
discard-and-reconstruct evaluation of FD-05 §8.

The corpus at Phase 3 is clean, so the axes here describe *legitimate*
variation (topology, scale, tagging discipline). Defect posture is deliberately
excluded — defects are injected in Phase 5 over the rendered estate, not chosen
here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum, StrEnum

from kgcr.hashing import canonical_hash

__all__ = [
    "Archetype",
    "AZSpread",
    "NetworkLayout",
    "LoggingPosture",
    "IAMShape",
    "TaggingDiscipline",
    "Scale",
    "Intent",
]


class Archetype(StrEnum):
    """The three workload archetypes (FD-05 §3, D2 resolved)."""

    PAYMENTS_API = "payments_api"
    CUSTOMER_DATA_PLATFORM = "customer_data_platform"
    INTERNAL_REPORTING = "internal_reporting"


class AZSpread(StrEnum):
    SINGLE_AZ = "single_az"
    TWO_AZ = "two_az"
    THREE_AZ = "three_az"


class NetworkLayout(StrEnum):
    PUBLIC_ONLY = "public_only"
    PUBLIC_PRIVATE = "public_private"
    PRIVATE_WITH_NAT = "private_with_nat"


class LoggingPosture(StrEnum):
    FULL = "full"
    MINIMAL = "minimal"


class IAMShape(StrEnum):
    LEAST_PRIVILEGE = "least_privilege"
    ROLE_PER_SERVICE = "role_per_service"


class TaggingDiscipline(StrEnum):
    """Tagging quality is legitimate variation, not a defect (FD-05 §4A)."""

    STRICT = "strict"
    PARTIAL = "partial"
    POOR = "poor"


class Scale(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# Data sensitivity is derived from the archetype, not sampled — it is a
# property of the workload, and later phases key compliance scope off it.
DATA_SENSITIVITY: dict[Archetype, str] = {
    Archetype.PAYMENTS_API: "cardholder_data",
    Archetype.CUSTOMER_DATA_PLATFORM: "pii",
    Archetype.INTERNAL_REPORTING: "low",
}


@dataclass(frozen=True, slots=True)
class Intent:
    """One point in the intent space — the ground truth for an estate.

    ``region`` is a plain string (sampled from a small set); every other axis is
    a closed enum so the space is enumerable and the reconstruction task (P8) is
    a well-defined classification per field.
    """

    archetype: Archetype
    region: str
    az_spread: AZSpread
    network_layout: NetworkLayout
    logging: LoggingPosture
    iam_shape: IAMShape
    tagging: TaggingDiscipline
    scale: Scale

    @property
    def data_sensitivity(self) -> str:
        return DATA_SENSITIVITY[self.archetype]

    def to_dict(self) -> dict[str, str]:
        """Plain ``{axis: value}`` dict, enum values unwrapped to strings."""
        out: dict[str, str] = {}
        for key, value in asdict(self).items():
            out[key] = value.value if isinstance(value, Enum) else value
        out["data_sensitivity"] = self.data_sensitivity
        return out

    @property
    def intent_hash(self) -> str:
        """Stable identity of this intent, independent of field order."""
        # data_sensitivity is derived, so exclude it from the identity to avoid
        # double-counting the archetype it comes from.
        identity = {k: v for k, v in self.to_dict().items() if k != "data_sensitivity"}
        return canonical_hash(identity)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Intent:
        """Rebuild from :meth:`to_dict` output; the derived field is ignored."""
        return cls(
            archetype=Archetype(data["archetype"]),
            region=data["region"],
            az_spread=AZSpread(data["az_spread"]),
            network_layout=NetworkLayout(data["network_layout"]),
            logging=LoggingPosture(data["logging"]),
            iam_shape=IAMShape(data["iam_shape"]),
            tagging=TaggingDiscipline(data["tagging"]),
            scale=Scale(data["scale"]),
        )
