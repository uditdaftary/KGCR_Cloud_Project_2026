"""Per-field accuracy and calibration for reconstruction (FD-05 §8).

Two numbers per field: how often the recovered value is right, and whether the
confidence behind it is honest. Calibration is reported **per field, never
pooled** — most axes are near-deterministic from topology and would swamp the
pooled curve at (1.0, 1.0), hiding the one axis that matters: ``iam_shape``,
which the generator leaves no structural trace of, so an honest reconstructor
must be visibly unconfident about it.

The reliability diagram is emitted as data (confidence bins vs empirical
accuracy) plus an expected-calibration-error summary — the numeric form of the
diagram, renderable to a plot with a few lines of matplotlib if wanted.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.reconstruction.reconstructor import RECONSTRUCTED_FIELDS, IntentReconstructor

__all__ = ["CalibrationBin", "FieldEvaluation", "ReconstructionReport", "evaluate_reconstruction"]


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    """One reliability-diagram bin for a field."""

    lower: float
    upper: float
    mean_confidence: float
    accuracy: float
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "mean_confidence": self.mean_confidence,
            "accuracy": self.accuracy,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class FieldEvaluation:
    """Accuracy and calibration for one reconstructed field."""

    field: str
    n: int
    accuracy: float
    mean_confidence: float
    expected_calibration_error: float
    bins: tuple[CalibrationBin, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "n": self.n,
            "accuracy": self.accuracy,
            "mean_confidence": self.mean_confidence,
            "expected_calibration_error": self.expected_calibration_error,
            "bins": [b.to_dict() for b in self.bins],
        }


@dataclass(frozen=True, slots=True)
class ReconstructionReport:
    """Per-field evaluation plus an overall accuracy."""

    per_field: dict[str, FieldEvaluation]
    overall_accuracy: float
    n_estates: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_estates": self.n_estates,
            "overall_accuracy": self.overall_accuracy,
            "per_field": {f: fe.to_dict() for f, fe in self.per_field.items()},
        }


def evaluate_reconstruction(
    reconstructor: IntentReconstructor,
    test_estates: Sequence[Estate],
    *,
    n_bins: int = 10,
) -> ReconstructionReport:
    """Evaluate ``reconstructor`` on held-out ``test_estates``.

    Compares each recovered field against the estate's known intent (the free
    ground truth of FD-05 §8) and bins the confidences per field for the
    reliability diagram.
    """
    if not test_estates:
        raise ValueError("cannot evaluate on an empty test set")

    # Per field: parallel lists of (confidence, was_correct).
    confidences: dict[str, list[float]] = {f: [] for f in RECONSTRUCTED_FIELDS}
    correct: dict[str, list[bool]] = {f: [] for f in RECONSTRUCTED_FIELDS}

    for estate in test_estates:
        truth = estate.intent.to_dict()
        predicted = reconstructor.reconstruct(estate)
        for field in RECONSTRUCTED_FIELDS:
            rf = predicted.fields[field]
            confidences[field].append(rf.confidence)
            correct[field].append(rf.value == truth[field])

    per_field: dict[str, FieldEvaluation] = {}
    for field in RECONSTRUCTED_FIELDS:
        per_field[field] = _evaluate_field(field, confidences[field], correct[field], n_bins)

    total = sum(fe.accuracy * fe.n for fe in per_field.values())
    denominator = sum(fe.n for fe in per_field.values())
    overall = total / denominator if denominator else 0.0
    return ReconstructionReport(
        per_field=per_field, overall_accuracy=overall, n_estates=len(test_estates)
    )


def _evaluate_field(
    field: str, confidences: list[float], correct: list[bool], n_bins: int
) -> FieldEvaluation:
    n = len(confidences)
    accuracy = sum(correct) / n if n else 0.0
    mean_conf = sum(confidences) / n if n else 0.0

    bins: list[CalibrationBin] = []
    ece = 0.0
    for i in range(n_bins):
        lower = i / n_bins
        upper = (i + 1) / n_bins
        # Last bin is closed on the right so confidence == 1.0 lands somewhere.
        members = [
            j
            for j, c in enumerate(confidences)
            if (lower <= c < upper) or (i == n_bins - 1 and c == upper)
        ]
        if not members:
            continue
        count = len(members)
        bin_conf = sum(confidences[j] for j in members) / count
        bin_acc = sum(1 for j in members if correct[j]) / count
        bins.append(CalibrationBin(lower, upper, bin_conf, bin_acc, count))
        ece += (count / n) * abs(bin_conf - bin_acc)

    return FieldEvaluation(
        field=field,
        n=n,
        accuracy=accuracy,
        mean_confidence=mean_conf,
        expected_calibration_error=ece,
        bins=tuple(bins),
    )
