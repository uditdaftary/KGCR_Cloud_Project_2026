"""Record the model responses the review variants still lack, inside a call budget.

Replay is free, so running this twice never repeats a call: a variant whose responses are
already committed costs nothing, and a stop on the daily quota or the budget leaves what was
recorded so far on disk for the next run.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from kgcr.advisor.llm import FixtureClient
from kgcr.orchestration.aws import ArtifactStore, Notifier
from kgcr.orchestration.review import run_review

__all__ = ["VARIANT_ORDER", "Recording", "record_variants"]

logger = logging.getLogger(__name__)

# The relational defects first: they are what the model is for, and the rule floor cannot see them.
VARIANT_ORDER = (
    "indirect_internet_reachability",
    "privilege_escalation_passrole",
    "transitive_trust_chain",
    "unencrypted_database",
    "open_security_group",
    "wildcard_iam_policy",
    "cloudtrail_no_log_validation",
    "unattached_volume",
    "no_database_backup",
)

_QUOTA_CODE = 429


@dataclass(frozen=True, slots=True)
class Recording:
    variant: str
    live_calls: int
    outcome: str  # replayed | recorded | quota | budget | failed: <why>


def _outcome(exc: Exception) -> str:
    # The SDK's APIError carries the HTTP status; checked by attribute so this module imports
    # without the optional google-genai extra.
    if getattr(exc, "code", None) == _QUOTA_CODE:
        return "quota"
    if isinstance(exc, RuntimeError) and "live call cap" in str(exc):
        return "budget"
    return f"failed: {type(exc).__name__}: {exc}"


def record_variants(
    variants: Sequence[str],
    *,
    client: FixtureClient,
    store: ArtifactStore,
    notifier: Notifier,
    count: int = 180,
    seed: int,
) -> list[Recording]:
    """Review each variant through ``client``; stop at the first quota or budget refusal."""
    done: list[Recording] = []
    for variant in variants:
        before = client.live_calls
        try:
            run_review(
                variant=variant,
                store=store,
                notifier=notifier,
                llm=client,
                count=count,
                seed=seed,
            )
        except Exception as exc:  # noqa: BLE001 - classified below, logged, never swallowed
            outcome = _outcome(exc)
            logger.warning("recording %s stopped: %s", variant, outcome)
        else:
            outcome = "recorded" if client.live_calls > before else "replayed"
        done.append(Recording(variant, client.live_calls - before, outcome))
        if outcome in ("quota", "budget"):
            break
    return done
