"""Read stored review runs back from a local artifact store (``<root>/runs/<prefix>/``).

Shared by ``kgcr history``, ``kgcr explain`` and the dashboard, so all three see the
same runs the same way. Runs from before ``summary.json`` existed still load; their
summary and timings are simply absent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kgcr.explainer.explainer import AUDIENCES, ExplanationBundle, extract_claims, render

__all__ = ["RunNotFound", "list_runs", "load_run", "resolve_run"]

# A run directory is the first 16 hex characters of its run_id.
_PREFIX = re.compile(r"^[0-9a-f]{4,64}$")


class RunNotFound(LookupError):
    """No stored run matches the requested id, or the id is ambiguous."""


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def list_runs(root: Path) -> list[dict[str, Any]]:
    """One row per stored run, newest first."""
    rows = []
    for run_dir in (root / "runs").glob("*/"):
        record, bundle = _read(run_dir / "run_record.json"), _read(run_dir / "bundle.json")
        if record is None or bundle is None:
            continue
        summary = _read(run_dir / "summary.json") or {}
        rows.append(
            {
                "prefix": run_dir.name,
                "run_id": record["run_id"],
                "created_at": record["created_at"],
                "seed": record["seed"],
                "model_version": record["model_version"],
                "estate_id": bundle["estate_id"],
                "loop_status": bundle["loop_status"],
                "loop_reason": bundle["loop_reason"],
                "severities": [f["severity"] for f in bundle["findings"]],
                "variant": summary.get("variant"),
                "llm_mode": summary.get("llm_mode"),
            }
        )
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)


def resolve_run(root: Path, run: str) -> Path:
    """The run directory whose id starts with ``run``; refuses non-hex input."""
    run = run.strip().lower()
    if not _PREFIX.match(run):
        raise RunNotFound(f"not a run id: {run!r}")
    matches = [
        p for p in (root / "runs").glob("*/") if run.startswith(p.name) or p.name.startswith(run)
    ]
    if not matches:
        raise RunNotFound(f"no stored run matches {run!r} under {root}")
    if len(matches) > 1:
        raise RunNotFound(f"{run!r} is ambiguous: {', '.join(sorted(p.name for p in matches))}")
    return matches[0]


def load_run(root: Path, run: str) -> dict[str, Any]:
    """Everything stored for one run, explanations re-rendered from its bundle."""
    run_dir = resolve_run(root, run)
    bundle_dict = _read(run_dir / "bundle.json")
    bundle = ExplanationBundle.from_dict(bundle_dict)
    explanations = {a: render(bundle, a) for a in AUDIENCES}
    return {
        "prefix": run_dir.name,
        "record": _read(run_dir / "run_record.json"),
        "bundle": bundle_dict,
        "summary": _read(run_dir / "summary.json"),
        "timings": _read(run_dir / "timings.json"),
        "explanations": explanations,
        # INV-2 made visible: the claims every rendering must share.
        "claims": {a: sorted(extract_claims(text)) for a, text in explanations.items()},
    }
