"""Reconstruct the intent of one estate using the fitted model.

Prints the recovered value and confidence for every intent axis. Confidence is
load-bearing, not decorative: a field below the escalation threshold is meant to
be confirmed with the user rather than assumed (FD-01 §7), so low-confidence
fields are flagged in the output.

The estate is regenerated from ``(seed, index)`` because generation is
deterministic — estate *i* here is the same estate *i* the corpus contains. Note
that an arbitrary index may fall in the training split, so the confidence shown
here is not a held-out measurement; ``train.py``'s report is.

    python src/ml_model/predict.py --index 0 --seed 0
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

from kgcr.corpus.pipeline import generate_corpus
from kgcr.reconstruction.pipeline import ESCALATION_THRESHOLD
from kgcr.reconstruction.reconstructor import IntentReconstructor
from kgcr.repro import DEFAULT_SEED

DEFAULT_MODEL = Path("src/ml_model/model.pkl")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=0, help="Estate index within the corpus")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Generation seed")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Fitted model path")
    args = parser.parse_args()

    if not args.model.exists():
        parser.error(f"{args.model} not found — run train.py first")

    # Trusted input: this file is written by train.py in this repository. Never
    # unpickle a model from an untrusted source.
    reconstructor: IntentReconstructor = pickle.loads(args.model.read_bytes())

    estate = generate_corpus(args.index + 1, args.seed)[args.index]
    recovered = reconstructor.reconstruct(estate)

    print(json.dumps(recovered.to_dict(), indent=2, sort_keys=True))
    low = recovered.low_confidence_fields(ESCALATION_THRESHOLD)
    if low:
        print(f"escalate (confidence < {ESCALATION_THRESHOLD}): {', '.join(sorted(low))}")
    print(f"true intent: {json.dumps(estate.intent.to_dict(), sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
