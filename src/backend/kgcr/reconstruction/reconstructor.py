"""A per-field classifier that recovers intent from estate structure.

One classifier per intent axis (FD-05 §8), each producing a predicted value and
a confidence from its class-probability estimate. ``region`` is not classified —
it is directly observable in a harvested account — so it is passed through as an
observed field with full confidence.

The confidence is load-bearing, not decorative: a field below the escalation
threshold must be confirmed with the user rather than assumed (FD-01 §7). The
reconstructor therefore exposes :meth:`ReconstructedIntent.low_confidence_fields`
for the escalation decision, and the evaluation (see :mod:`.evaluate`) checks
that those confidences are calibrated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from kgcr.corpus.estate import Estate
from kgcr.reconstruction.features import feature_vector

__all__ = [
    "RECONSTRUCTED_FIELDS",
    "ReconstructedField",
    "ReconstructedIntent",
    "IntentReconstructor",
]

# The intent axes reconstructed from topology. ``region`` is excluded — it is
# read directly from the account, not inferred.
RECONSTRUCTED_FIELDS: tuple[str, ...] = (
    "archetype",
    "az_spread",
    "network_layout",
    "logging",
    "iam_shape",
    "tagging",
    "scale",
)


@dataclass(frozen=True, slots=True)
class ReconstructedField:
    """A recovered axis value and the confidence behind it."""

    value: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ReconstructedIntent:
    """A reconstructed intent: observed region plus per-field predictions."""

    region: str
    fields: dict[str, ReconstructedField]

    def value(self, field: str) -> str:
        return self.fields[field].value

    def confidence(self, field: str) -> float:
        return self.fields[field].confidence

    def low_confidence_fields(self, threshold: float) -> list[str]:
        """Fields whose confidence is below ``threshold`` — escalate these."""
        return [f for f, rf in self.fields.items() if rf.confidence < threshold]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "fields": {
                f: {"value": rf.value, "confidence": rf.confidence} for f, rf in self.fields.items()
            },
        }


class IntentReconstructor:
    """Fits one classifier per intent axis over structural features."""

    def __init__(self, random_state: int = 0) -> None:
        self._random_state = random_state
        self._models: dict[str, Any] = {}

    @property
    def fitted(self) -> bool:
        return bool(self._models)

    def fit(self, estates: Sequence[Estate]) -> None:
        """Train a classifier per field on the estates' known intents.

        Training reads ``estate.intent`` — the supervised labels — which is
        legitimate: FD-05 §8's discard-and-reconstruct applies to *evaluation*,
        and estate-level splitting (done by the caller) keeps the test intents
        out of training.
        """
        if not estates:
            raise ValueError("cannot fit on an empty estate set")
        features = np.array([feature_vector(e) for e in estates], dtype=float)
        for field in RECONSTRUCTED_FIELDS:
            labels = [e.intent.to_dict()[field] for e in estates]
            model = RandomForestClassifier(n_estimators=200, random_state=self._random_state)
            model.fit(features, labels)
            self._models[field] = model

    def reconstruct(self, estate: Estate) -> ReconstructedIntent:
        """Recover the intent of ``estate`` from its structure alone."""
        if not self.fitted:
            raise RuntimeError("reconstructor is not fitted; call fit() first")
        x = np.array([feature_vector(estate)], dtype=float)
        fields: dict[str, ReconstructedField] = {}
        for field, model in self._models.items():
            proba = model.predict_proba(x)[0]
            best = int(np.argmax(proba))
            fields[field] = ReconstructedField(
                value=str(model.classes_[best]),
                confidence=float(proba[best]),
            )
        return ReconstructedIntent(region=estate.region, fields=fields)
