"""Structured intent intake (FD-01 S1a).

Every axis must be stated. A missing or invalid one is refused and named; nothing is
defaulted, because an unstated requirement silently assumed is the failure FD-01 forbids.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from kgcr.corpus.intent import (
    Archetype,
    AZSpread,
    IAMShape,
    Intent,
    LoggingPosture,
    NetworkLayout,
    Scale,
    TaggingDiscipline,
)
from kgcr.corpus.sampler import REGIONS

__all__ = ["AXES", "IntakeError", "axis_choices", "build_intent"]

AXES: tuple[str, ...] = (
    "archetype",
    "region",
    "az_spread",
    "network_layout",
    "logging",
    "iam_shape",
    "tagging",
    "scale",
)

_ENUMS: dict[str, type[StrEnum]] = {
    "archetype": Archetype,
    "az_spread": AZSpread,
    "network_layout": NetworkLayout,
    "logging": LoggingPosture,
    "iam_shape": IAMShape,
    "tagging": TaggingDiscipline,
    "scale": Scale,
}


class IntakeError(ValueError):
    """The intent is incomplete or holds a value outside the schema."""

    def __init__(self, missing: tuple[str, ...], invalid: dict[str, str]) -> None:
        self.missing = missing
        self.invalid = invalid
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if invalid:
            parts.append("invalid: " + ", ".join(f"{k}={v!r}" for k, v in sorted(invalid.items())))
        super().__init__("; ".join(parts))


def axis_choices() -> dict[str, tuple[str, ...]]:
    """The allowed values per axis, in axis order (the form and the CLI both read this)."""
    out: dict[str, tuple[str, ...]] = {}
    for axis in AXES:
        out[axis] = REGIONS if axis == "region" else tuple(m.value for m in _ENUMS[axis])
    return out


def build_intent(values: Mapping[str, str | None]) -> Intent:
    """An :class:`Intent` from stated values; raises :class:`IntakeError` naming every problem."""
    choices = axis_choices()
    missing = tuple(a for a in AXES if values.get(a) in (None, ""))
    invalid = {
        a: str(v)
        for a, v in values.items()
        if v not in (None, "") and (a not in choices or v not in choices[a])
    }
    for key in values:
        if key not in choices:
            invalid[key] = "not an intent axis"
    if missing or invalid:
        raise IntakeError(missing, invalid)
    v = {a: str(values[a]) for a in AXES}  # every axis is present and valid past this point
    return Intent(
        archetype=Archetype(v["archetype"]),
        region=v["region"],
        az_spread=AZSpread(v["az_spread"]),
        network_layout=NetworkLayout(v["network_layout"]),
        logging=LoggingPosture(v["logging"]),
        iam_shape=IAMShape(v["iam_shape"]),
        tagging=TaggingDiscipline(v["tagging"]),
        scale=Scale(v["scale"]),
    )
