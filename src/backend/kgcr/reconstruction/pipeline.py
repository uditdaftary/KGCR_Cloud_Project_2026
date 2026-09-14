"""Run the reconstruction experiment: split, fit, evaluate (FD-05 §8).

Ties the pieces into the reportable experiment of the roadmap P8 gate —
round-trip fidelity plus a reliability diagram — on an estate-level split so no
estate's structure informs its own evaluation (FD-05 §9). The split is the same
:func:`~kgcr.corpus.splits.split_estates` used everywhere else, so reconstruction
honours the identical leakage guarantee the recommender does.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.corpus.splits import split_estates
from kgcr.reconstruction.evaluate import ReconstructionReport, evaluate_reconstruction
from kgcr.reconstruction.reconstructor import IntentReconstructor

__all__ = ["ExperimentResult", "run_reconstruction_experiment", "write_report"]

# Fields below this confidence escalate to user confirmation (FD-01 §7).
ESCALATION_THRESHOLD = 0.6


class ExperimentResult:
    """A fitted reconstructor, its report, and the escalation summary."""

    def __init__(
        self,
        reconstructor: IntentReconstructor,
        report: ReconstructionReport,
        escalated_fields: list[str],
        n_train: int,
    ) -> None:
        self.reconstructor = reconstructor
        self.report = report
        self.escalated_fields = escalated_fields
        self.n_train = n_train

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_train": self.n_train,
            "escalation_threshold": ESCALATION_THRESHOLD,
            "escalated_fields": self.escalated_fields,
            "report": self.report.to_dict(),
        }


def run_reconstruction_experiment(
    estates: Sequence[Estate],
    *,
    random_state: int = 0,
) -> ExperimentResult:
    """Fit on the train+validation split and evaluate on the held-out test split."""
    split = split_estates(estates)
    by_id = {e.estate_id: e for e in estates}
    fit_ids = set(split.train.estate_ids) | set(split.validation.estate_ids)
    train = [by_id[i] for i in fit_ids if i in by_id]
    test = [by_id[i] for i in split.test.estate_ids if i in by_id]
    if not train or not test:
        raise ValueError("split produced an empty train or test set; supply more estates")

    reconstructor = IntentReconstructor(random_state=random_state)
    reconstructor.fit(train)
    report = evaluate_reconstruction(reconstructor, test)

    escalated = sorted(
        f for f, fe in report.per_field.items() if fe.mean_confidence < ESCALATION_THRESHOLD
    )
    return ExperimentResult(reconstructor, report, escalated, n_train=len(train))


def write_report(result: ExperimentResult, path: str | Path) -> Path:
    """Write the experiment result as JSON, returning the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return out
