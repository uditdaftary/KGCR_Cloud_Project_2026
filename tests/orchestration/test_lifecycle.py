"""The lifecycle log only ever grows, and only with known events."""

from __future__ import annotations

from pathlib import Path

import pytest

from kgcr.orchestration.lifecycle import append_event, read_events


def test_no_log_reads_as_empty(tmp_path: Path) -> None:
    assert read_events(tmp_path / "runs" / "abcd") == []


def test_events_append_in_order_and_never_rewrite_earlier_ones(tmp_path: Path) -> None:
    first = append_event(tmp_path, "abcd1234abcd1234", "designed")
    second = append_event(tmp_path, "abcd1234abcd1234", "planned", plan_id="p" * 16)
    assert [e["event"] for e in second] == ["designed", "planned"]
    assert second[0] == first[0]
    assert second[1]["plan_id"] == "p" * 16
    assert read_events(tmp_path / "runs" / "abcd1234abcd1234") == second


def test_unknown_event_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown lifecycle event"):
        append_event(tmp_path, "abcd1234abcd1234", "deployed")
    assert not (tmp_path / "runs").exists()


def test_a_key_that_escapes_the_store_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_event(tmp_path, "../outside", "designed")
