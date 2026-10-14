"""Helpers shared by the review and design pipelines."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from kgcr.advisor.controls import DRAFT_CONTROLS_PATH

__all__ = ["StageClock", "graph_version", "to_json"]


def graph_version() -> str:
    """The L1 encoding in force, pinned by the controls file's bytes (FD-03 section 7)."""
    digest = hashlib.sha256(DRAFT_CONTROLS_PATH.read_bytes()).hexdigest()[:12]
    return f"l1-draft-{digest}"


def to_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


class StageClock:
    """Wall-clock seconds per pipeline stage, measured between successive marks."""

    def __init__(self) -> None:
        self._last = time.perf_counter()
        self.stages: list[dict[str, Any]] = []

    def mark(self, stage: str) -> None:
        now = time.perf_counter()
        self.stages.append({"stage": stage, "seconds": round(now - self._last, 4)})
        self._last = now
