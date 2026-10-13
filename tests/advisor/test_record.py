"""The variant recorder stops where it must and never repeats a recorded call."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from kgcr.advisor.llm import FixtureClient  # noqa: E402
from kgcr.advisor.record import VARIANT_ORDER, record_variants  # noqa: E402
from kgcr.defects.inject import INJECTORS  # noqa: E402
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier  # noqa: E402

COUNT = 60


class _QuotaError(Exception):
    code = 429


class _Live:
    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc
        self.calls = 0

    def complete(self, prompt: str, label: str) -> str:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return "[]"


def _record(tmp_path: Path, live: _Live, variants: tuple[str, ...], budget: int):  # type: ignore[no-untyped-def]
    client = FixtureClient(tmp_path / "fixtures", live, max_live_calls=budget)
    out = record_variants(
        variants,
        client=client,
        store=LocalArtifactStore(tmp_path / "runs"),
        notifier=LogNotifier(),
        count=COUNT,
        seed=1729,
    )
    return client, out


def test_the_order_covers_every_variant_with_the_relational_ones_first() -> None:
    assert set(VARIANT_ORDER) == {i.variant for i in INJECTORS}
    assert VARIANT_ORDER[:2] == ("indirect_internet_reachability", "privilege_escalation_passrole")


def test_a_daily_quota_refusal_stops_the_run_after_one_call(tmp_path: Path) -> None:
    live = _Live(_QuotaError("RESOURCE_EXHAUSTED"))
    _, out = _record(tmp_path, live, ("unencrypted_database", "open_security_group"), budget=10)
    assert [(r.variant, r.outcome, r.live_calls) for r in out] == [
        ("unencrypted_database", "quota", 1)
    ]
    assert live.calls == 1


def test_the_budget_is_a_hard_ceiling_and_what_was_recorded_stays(tmp_path: Path) -> None:
    live = _Live()
    client, out = _record(tmp_path, live, ("unencrypted_database", "open_security_group"), budget=1)
    assert live.calls == 1 and client.live_calls == 1
    assert len(list((tmp_path / "fixtures").glob("*.json"))) == 1
    assert out[-1].outcome in ("budget", "recorded")


def test_a_second_run_over_the_same_fixtures_makes_no_calls(tmp_path: Path) -> None:
    first = _Live()
    _record(tmp_path, first, ("unencrypted_database",), budget=5)
    second = _Live()
    _, out = _record(tmp_path, second, ("unencrypted_database",), budget=5)
    assert second.calls == 0 and out[0].outcome == "replayed" and out[0].live_calls == 0
