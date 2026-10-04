"""Run the P7 recommender experiment and write its report.

Fits the option recommender on train+validation (with that side's defect corpus
as the retrieval pool), evaluates it and three baselines on the held-out test
split, and writes ``results/recommender_report.json``. No model file is written:
fitting takes seconds and is deterministic, so callers refit rather than unpickle.

    python src/ml_model/train_recommender.py --count 180 --seed 1729
"""

from __future__ import annotations

import argparse
from pathlib import Path

from kgcr.corpus.pipeline import generate_corpus
from kgcr.recommender.evaluate import run_recommender_experiment, write_report
from kgcr.repro import DEFAULT_SEED, seed_everything

DEFAULT_REPORT = Path("results/recommender_report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180, help="Number of estates (default 180)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Generation seed")
    parser.add_argument("--random-state", type=int, default=0, help="Classifier random_state")
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT, help="Report path")
    args = parser.parse_args()

    seed_everything(args.seed)
    experiment = run_recommender_experiment(
        generate_corpus(args.count, args.seed), random_state=args.random_state
    )
    report = experiment.report
    print(f"n_fit={report['n_fit']} n_test={report['n_test']} pool={report['n_pool_after_mask']}")
    for name, m in report["rankers"].items():
        print(
            f"{name:28s} ndcg={m['ndcg']:.3f} p@10={m['p_at_10']:.3f} "
            f"r_prec={m['r_precision']:.3f} exact_set={m['exact_set']:.3f}"
        )
    print(f"masked (CRITICAL): {len(report['masked_critical'])}")
    print(f"report: {write_report(experiment, args.report_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
