"""Run the P6 advisor evaluation and write ``results/advisor_report.json``.

Without recorded fixtures or live opt-in the LLM section reads NOT_RUN. To record
fixtures (at most ``LIVE_CALL_CAP`` Gemini calls, free tier), set ``GEMINI_API_KEY``
and ``KGCR_LLM_LIVE=1`` in the environment, then:

    python src/ml_model/run_advisor.py --count 180 --seed 1729
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from kgcr.advisor.evaluate import run_advisor_evaluation, write_report
from kgcr.advisor.llm import DEFAULT_FIXTURE_DIR, FixtureClient, LLMClient, live_client_from_env
from kgcr.corpus.pipeline import generate_corpus
from kgcr.repro import DEFAULT_SEED, seed_everything

DEFAULT_REPORT = Path("results/advisor_report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180, help="Number of estates (default 180)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Generation seed")
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT, help="Report path")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    seed_everything(args.seed)
    live = live_client_from_env()
    llm: LLMClient | None = None
    if live is not None or DEFAULT_FIXTURE_DIR.exists():
        llm = FixtureClient(DEFAULT_FIXTURE_DIR, live)
    report = run_advisor_evaluation(generate_corpus(args.count, args.seed), llm)
    print(json.dumps({k: report[k] for k in ("rule_floor", "llm", "sycophancy_gate")}, indent=1))
    print(f"report: {write_report(report, args.report_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
