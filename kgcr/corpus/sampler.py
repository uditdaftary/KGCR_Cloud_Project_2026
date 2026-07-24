"""Seeded, reproducible sampling of intents from the archetype space.

The sampler draws an archetype, then draws each parameter axis from an
archetype-conditioned distribution: a payments API skews toward multi-AZ,
private networking, full logging and strict tagging; internal reporting — the
cost-dominant contrast case (FD-05 §3) — skews the other way. The distributions
are weights, not hard rules, so the space stays diverse.

Every draw goes through a single :class:`random.Random` seeded per sampler, so a
given seed reproduces the exact same intent stream (PMD reproducibility track).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import TypeVar

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
from kgcr.repro import DEFAULT_SEED

__all__ = ["IntentSampler", "REGIONS"]

# A small region set keeps the categorical space tractable for reconstruction.
REGIONS: tuple[str, ...] = ("eu-west-1", "eu-west-2", "us-east-1")

_T = TypeVar("_T")

# Per-archetype weightings. Each maps an axis value to a relative weight; unlisted
# values default to weight 1. The intent is "typical, not mandatory".
_ARCHETYPE_WEIGHTS: dict[Archetype, float] = {
    Archetype.PAYMENTS_API: 1.0,
    Archetype.CUSTOMER_DATA_PLATFORM: 1.0,
    Archetype.INTERNAL_REPORTING: 1.0,
}


class IntentSampler:
    """Draws :class:`Intent` values reproducibly from a seeded RNG."""

    def __init__(self, seed: int = DEFAULT_SEED) -> None:
        if seed < 0:
            raise ValueError(f"seed must be non-negative, got {seed}")
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def seed(self) -> int:
        return self._seed

    def _weighted(self, values: Sequence[_T], weights: Sequence[float]) -> _T:
        return self._rng.choices(list(values), weights=list(weights), k=1)[0]

    def _choice(self, values: Sequence[_T]) -> _T:
        return self._rng.choice(list(values))

    def sample_archetype(self) -> Archetype:
        archetypes = list(_ARCHETYPE_WEIGHTS)
        weights = [_ARCHETYPE_WEIGHTS[a] for a in archetypes]
        return self._weighted(archetypes, weights)

    def sample(self, archetype: Archetype | None = None) -> Intent:
        """Sample one intent, optionally forcing the archetype."""
        arch = archetype if archetype is not None else self.sample_archetype()
        return Intent(
            archetype=arch,
            region=self._choice(REGIONS),
            az_spread=self._sample_az_spread(arch),
            network_layout=self._sample_network(arch),
            logging=self._sample_logging(arch),
            iam_shape=self._choice(list(IAMShape)),
            tagging=self._sample_tagging(arch),
            scale=self._sample_scale(arch),
        )

    # --- archetype-conditioned axes ------------------------------------------

    def _sample_az_spread(self, arch: Archetype) -> AZSpread:
        values = list(AZSpread)
        if arch is Archetype.PAYMENTS_API:
            weights = [1.0, 3.0, 4.0]  # skew multi-AZ
        elif arch is Archetype.INTERNAL_REPORTING:
            weights = [5.0, 2.0, 1.0]  # skew single-AZ (cost)
        else:
            weights = [2.0, 3.0, 3.0]
        return self._weighted(values, weights)

    def _sample_network(self, arch: Archetype) -> NetworkLayout:
        values = list(NetworkLayout)
        if arch is Archetype.PAYMENTS_API:
            weights = [1.0, 3.0, 4.0]  # prefer private
        elif arch is Archetype.INTERNAL_REPORTING:
            weights = [3.0, 3.0, 1.0]
        else:
            weights = [1.0, 4.0, 3.0]
        return self._weighted(values, weights)

    def _sample_logging(self, arch: Archetype) -> LoggingPosture:
        values = list(LoggingPosture)
        if arch is Archetype.INTERNAL_REPORTING:
            weights = [2.0, 3.0]  # more likely minimal
        else:
            weights = [4.0, 1.0]  # regulated: prefer full
        return self._weighted(values, weights)

    def _sample_tagging(self, arch: Archetype) -> TaggingDiscipline:
        values = list(TaggingDiscipline)
        if arch is Archetype.INTERNAL_REPORTING:
            weights = [1.0, 2.0, 2.0]  # laxer
        else:
            weights = [3.0, 2.0, 1.0]
        return self._weighted(values, weights)

    def _sample_scale(self, arch: Archetype) -> Scale:
        values = list(Scale)
        if arch is Archetype.PAYMENTS_API:
            weights = [1.0, 3.0, 3.0]
        elif arch is Archetype.INTERNAL_REPORTING:
            weights = [4.0, 2.0, 1.0]
        else:
            weights = [2.0, 3.0, 2.0]
        return self._weighted(values, weights)
