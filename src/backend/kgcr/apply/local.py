"""A simulated apply into the local artifact store (FD-01 S10, local backend).

Nothing here touches a cloud. It exists so the plan, apply and lifecycle semantics can be
exercised and shown without spending anything, and it enforces the same invariants the real
path does:

* INV-3: an apply takes a plan id, loads that stored plan, and recomputes the spec's hash.
  If the stored spec is not the one that was planned, it refuses.
* a plan is applied once; a failed attempt may be retried;
* a failure partway leaves a recorded partial state, not nothing (FD-01 S10).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kgcr.apply import ApplyRefused
from kgcr.corpus.tfjson import resources_from_terraform_json
from kgcr.orchestration.aws import LocalArtifactStore
from kgcr.orchestration.common import to_json
from kgcr.orchestration.lifecycle import append_event, read_events
from kgcr.plan.deployable import document_hash
from kgcr.plan.local import PlanRefused, load_plan

__all__ = ["apply_local", "reviewed_plan"]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def reviewed_plan(store_root: Path, plan_id: str) -> tuple[dict[str, Any], Path]:
    """The stored plan and its run directory, after the INV-3 check that the spec is unchanged."""
    try:
        plan = load_plan(store_root, plan_id)
    except PlanRefused as exc:
        raise ApplyRefused(f"no apply without a plan (INV-3): {exc}") from exc
    run_dir = store_root / "runs" / plan["run_prefix"]
    spec_path = run_dir / "patched_spec.tf.json"
    if not spec_path.exists():
        raise ApplyRefused("the run's stored spec is missing")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if document_hash(spec) != plan["spec_hash"]:
        raise ApplyRefused("the stored spec changed after it was planned; plan it again (INV-3)")
    return plan, run_dir


def apply_local(store_root: Path, plan_id: str, *, fail_after: int | None = None) -> dict[str, Any]:
    """Simulate applying ``plan_id``. ``fail_after`` is a fault-injection seam for tests."""
    plan, run_dir = reviewed_plan(store_root, plan_id)
    if any(e["event"] == "applied" and e.get("plan_id") == plan_id for e in read_events(run_dir)):
        raise ApplyRefused(f"plan {plan_id} was already applied")

    steps = [
        *({"address": a, "action": "create"} for a in plan["creates"]),
        *({"address": m["address"], "action": "modify"} for m in plan["modifies"]),
        *({"address": a, "action": "destroy"} for a in plan["destroys"]),
    ]
    baseline: set[str] = set()
    if plan["baseline_kind"] == "observed":
        observed = json.loads((run_dir / "observed_spec.tf.json").read_text(encoding="utf-8"))
        baseline = {r.address for r in resources_from_terraform_json(observed)}

    prefix = plan["run_prefix"]
    append_event(store_root, prefix, "apply_started", plan_id=plan_id, backend="local")
    started = _now()
    present = set(baseline)
    error: str | None = None
    for index, step in enumerate(steps):
        if fail_after is not None and index >= fail_after:
            step["status"] = "failed" if index == fail_after else "not_run"
            if index == fail_after:
                error = f"simulated failure at {step['address']}"
            continue
        step["status"] = "done"
        if step["action"] == "create":
            present.add(step["address"])
        elif step["action"] == "destroy":
            present.discard(step["address"])
    status = "failed" if error else "applied"

    record: dict[str, Any] = {
        "plan_id": plan_id,
        "run_prefix": prefix,
        "backend": "local",
        "simulated": True,
        "status": status,
        "error": error,
        "steps": steps,
        "started_at": started,
        "finished_at": _now(),
    }
    store = LocalArtifactStore(store_root)
    base = f"runs/{prefix}/applied/{plan_id}"
    store.put(f"{base}/apply.json", to_json(record))
    store.put(f"{base}/state.json", to_json({"plan_id": plan_id, "resources": sorted(present)}))
    append_event(
        store_root,
        prefix,
        "applied" if status == "applied" else "apply_failed",
        plan_id=plan_id,
        backend="local",
    )
    return record
