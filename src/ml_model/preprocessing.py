"""Generate the reconstruction corpus and write it to ``dataset/processed/``.

Entry point for the data-preparation step of the ML pipeline. The corpus is
generated, not downloaded: an intent is sampled first and a clean estate is
rendered from it, so every estate carries its originating intent as ground truth
(FD-05 §4A). Generation is deterministic in ``(count, seed)``, which is why the
corpus is reproducible from this command rather than committed as a blob.

    python src/ml_model/preprocessing.py --count 180 --seed 0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kgcr.corpus.pipeline import generate_corpus, write_corpus
from kgcr.repro import DEFAULT_SEED, seed_everything

DEFAULT_OUT = Path("dataset/processed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180, help="Number of estates (default 180)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Generation seed")
    parser.add_argument("--family-size", type=int, default=1, help="Estates per seed family")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    args = parser.parse_args()

    seed_everything(args.seed)
    estates = generate_corpus(args.count, args.seed, family_size=args.family_size)
    manifest = write_corpus(estates, args.out)
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
    print(f"corpus written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
