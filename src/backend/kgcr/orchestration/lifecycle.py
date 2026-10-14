"""The append-only event log beside a run: designed, planned, applied.

Kept apart from ``RunRecord`` on purpose: a run's identity is the hash of what produced
it, and planning or applying it later must not change that identity. Events are only ever
added; the file is rewritten whole (one writer, because dashboard jobs run one at a time).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kgcr.orchestration.aws import LocalArtifactStore
from kgcr.orchestration.common import to_json

__all__ = ["EVENTS", "append_event", "read_events"]

EVENTS = ("designed", "planned", "apply_started", "applied", "apply_failed")


def read_events(run_dir: Path) -> list[dict[str, Any]]:
    """The run's events in the order they happened; empty when none were recorded."""
    path = run_dir / "lifecycle.json"
    if not path.exists():
        return []
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError(f"{path} must hold a list of events")
    return [dict(e) for e in events]


def append_event(store_root: Path, prefix: str, event: str, **detail: Any) -> list[dict[str, Any]]:
    """Add one event to ``runs/<prefix>/lifecycle.json`` and return the whole log."""
    if event not in EVENTS:
        raise ValueError(f"unknown lifecycle event {event!r}; expected one of {EVENTS}")
    events = read_events(store_root / "runs" / prefix)
    events.append({"event": event, "at": datetime.now(UTC).isoformat(timespec="seconds"), **detail})
    LocalArtifactStore(store_root).put(f"runs/{prefix}/lifecycle.json", to_json(events))
    return events
