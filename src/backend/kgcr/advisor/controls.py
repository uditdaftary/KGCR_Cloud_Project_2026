"""The L1 control slice the advisor grounds findings in (FD-04 section 4, FD-07).

The slice is a DRAFT authored by Claude and pending Udit's review: FD-07 section 2
lets a model read L1 but never author it. Every entry carries ``verified`` so the
draft status is visible wherever a control is used, and the advisor report counts
unverified controls rather than hiding them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kgcr.defects.taxonomy import Severity

__all__ = ["Control", "DRAFT_CONTROLS_PATH", "load_controls"]

DRAFT_CONTROLS_PATH = Path(__file__).with_name("controls_DRAFT-FOR-UDIT-REVIEW.json")


@dataclass(frozen=True, slots=True)
class Control:
    """One L1 control node. Severity is derived from its classification, never asserted."""

    control_node: str
    control_ref: str
    classification: str
    summary: str
    severity: Severity
    verified: bool


def load_controls(path: Path = DRAFT_CONTROLS_PATH) -> dict[str, Control]:
    """Load the control slice, keyed by ``control_node``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    to_severity = {k: Severity(v) for k, v in data["classification_to_severity"].items()}
    controls: dict[str, Control] = {}
    for entry in data["controls"]:
        node = entry["control_node"]
        if node in controls:
            raise ValueError(f"duplicate control node {node} in {path}")
        controls[node] = Control(
            control_node=node,
            control_ref=entry["control_ref"],
            classification=entry["classification"],
            summary=entry["summary"],
            severity=to_severity[entry["classification"]],
            verified=bool(entry["verified"]),
        )
    return controls
