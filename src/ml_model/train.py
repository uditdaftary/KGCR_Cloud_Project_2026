"""Fit the intent reconstructor and write ``model.pkl`` plus its evaluation.

Runs the P8 experiment: estate-level split, fit one RandomForest per intent axis
on train+validation, evaluate on the held-out test split with per-field accuracy
and calibration (never pooled). The corpus is regenerated from ``(count, seed)``
rather than read from disk — generation is deterministic, so this trains on
exactly the corpus ``preprocessing.py`` wrote for the same arguments.

    python src/ml_model/train.py --count 180 --seed 0
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

from kgcr.corpus.pipeline import generate_corpus
from kgcr.reconstruction.pipeline import run_reconstruction_experiment, write_report
from kgcr.repro import DEFAULT_SEED, seed_everything

DEFAULT_MODEL = Path("src/ml_model/model.pkl")
DEFAULT_REPORT = Path("results/reconstruction_report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180, help="Number of estates (default 180)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Generation seed")
    # Kept separate from --seed: the corpus seed and the forest's random_state are
    # independent knobs, and random_state=0 is what the recorded P8 result used.
    parser.add_argument("--random-state", type=int, default=0, help="Classifier random_state")
    parser.add_argument("--model-out", type=Path, default=DEFAULT_MODEL, help="Model path")
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT, help="Report path")
    args = parser.parse_args()

    seed_everything(args.seed)
    estates = generate_corpus(args.count, args.seed)
    result = run_reconstruction_experiment(estates, random_state=args.random_state)

    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    args.model_out.write_bytes(pickle.dumps(result.reconstructor))
    report_path = write_report(result, args.report_out)

    for field, entry in sorted(result.report.per_field.items()):
        print(
            f"{field:16s} accuracy={entry.accuracy:.3f} "
            f"ece={entry.expected_calibration_error:.3f}"
        )
    if result.escalated_fields:
        print(f"escalate (low confidence): {', '.join(result.escalated_fields)}")
    # ASCII only: the default Windows console encoding (cp1252) cannot encode
    # arrows and raises UnicodeEncodeError on print.
    print(f"model:  {args.model_out}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
