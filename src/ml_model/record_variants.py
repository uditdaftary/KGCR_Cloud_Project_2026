"""Record Gemini responses for the review variants that have none yet (free tier, budgeted).

Needs ``GEMINI_API_KEY`` and ``KGCR_LLM_LIVE=1``. Replay is free, so this is safe to run
repeatedly; it stops at the first daily-quota refusal or when ``--budget`` live calls are
used, and keeps what it recorded. The free tier allows about 20 requests a day.

    python src/ml_model/record_variants.py --budget 18
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from kgcr.advisor.llm import (
    DEFAULT_FIXTURE_DIR,
    FixtureClient,
    live_client_from_env,
    load_local_env,
)
from kgcr.advisor.record import VARIANT_ORDER, record_variants
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier
from kgcr.repro import DEFAULT_SEED


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=18, help="Most live calls this run may make")
    parser.add_argument("--count", type=int, default=180)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    load_local_env()
    live = live_client_from_env()
    if live is None:
        print("set GEMINI_API_KEY and KGCR_LLM_LIVE=1 to record", file=sys.stderr)
        return 2
    client = FixtureClient(DEFAULT_FIXTURE_DIR, live, max_live_calls=args.budget)
    with tempfile.TemporaryDirectory() as tmp:
        recordings = record_variants(
            VARIANT_ORDER,
            client=client,
            store=LocalArtifactStore(Path(tmp)),
            notifier=LogNotifier(),
            count=args.count,
            seed=args.seed,
        )
    for r in recordings:
        print(f"{r.variant:<34} {r.outcome:<10} live calls {r.live_calls}")
    print(f"live calls this run: {client.live_calls} of {args.budget}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
