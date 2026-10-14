"""``kgcr plan`` (FD-01 S9): an immutable dry-run diff of a stored run's spec.

A plan reports what would change, not a verdict on whether to change it:

* creates, destroys and modifies (with the attribute before and after);
* control coverage: single-resource findings by severity before and after, and which
  were fixed or introduced;
* blast radius: everything that transitively depends on a modified or destroyed resource;
* cost: the monthly list-price delta, with what it leaves out (``plan.cost``).

Refusals are part of the contract. INV-1: a run whose advisor loop did not converge, or that
still has a CRITICAL finding, never reaches a plan. A run stored before observed specs were
kept cannot be diffed against reality, and says so.

A plan is written once under ``runs/<prefix>/plans/<plan_id>/plan.json``; asking again
returns the stored one. Its id covers the spec, the baseline and the backend, so a changed
input is a different plan.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from kgcr.corpus.resources import Resource
from kgcr.corpus.tfjson import resources_from_terraform_json
from kgcr.defects.detectors import resource_findings
from kgcr.defects.taxonomy import DEFAULT_CONTROL, DEFAULT_SEVERITY
from kgcr.hashing import canonical_hash
from kgcr.orchestration.aws import LocalArtifactStore
from kgcr.orchestration.common import to_json
from kgcr.orchestration.lifecycle import append_event
from kgcr.orchestration.runstore import resolve_run
from kgcr.plan.cost import UnknownRegion, estimate
from kgcr.plan.deployable import document_hash, terraform_document
from kgcr.plan.terraform_backend import (
    SubprocessRunner,
    TerraformError,
    TerraformRunner,
    plan_document,
    terraform_available,
)

__all__ = ["BACKENDS", "PlanRefused", "load_plan", "make_plan"]

BACKENDS = ("local", "terraform")
_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "ADVISORY")


class PlanRefused(RuntimeError):
    """The run cannot be planned; the message says why and what to do."""


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _refuse_unless_clean(summary: Mapping[str, Any]) -> None:
    loop = summary.get("loop") or {}
    if loop.get("status") != "CONVERGED":
        raise PlanRefused(
            f"the advisor loop ended {loop.get('status')} ({loop.get('reason')}); a spec "
            "with an unresolved finding is not planned (INV-1)"
        )
    final = (loop.get("passes") or [{}])[-1].get("findings", [])
    open_critical = [f for f in final if f.get("severity") == "CRITICAL"]
    if open_critical:
        raise PlanRefused(f"{len(open_critical)} CRITICAL finding(s) are still open (INV-1)")


def _slot(res: Resource) -> tuple[dict[str, Any], list[str]]:
    return res.attributes, sorted(res.references)


def _diff(
    base: Mapping[str, Resource], spec: Mapping[str, Resource]
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    creates = sorted(set(spec) - set(base))
    destroys = sorted(set(base) - set(spec))
    modifies: list[dict[str, Any]] = []
    for address in sorted(set(base) & set(spec)):
        if _slot(base[address]) == _slot(spec[address]):
            continue
        before, after = base[address].attributes, spec[address].attributes
        changes = [
            {"attribute": key, "before": before.get(key), "after": after.get(key)}
            for key in sorted(set(before) | set(after))
            if before.get(key) != after.get(key)
        ]
        if sorted(base[address].references) != sorted(spec[address].references):
            changes.append(
                {
                    "attribute": "references",
                    "before": sorted(base[address].references),
                    "after": sorted(spec[address].references),
                }
            )
        modifies.append({"address": address, "changes": changes})
    return creates, destroys, modifies


def _findings(resources: Iterable[Resource]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for res in resources:
        for f in resource_findings(res):
            out[(res.address, f.rule_id)] = {
                "address": res.address,
                "rule": f.rule_id,
                "control": DEFAULT_CONTROL[f.defect_class],
                "severity": DEFAULT_SEVERITY[f.defect_class].value,
            }
    return out


def _coverage(base: Iterable[Resource], spec: Iterable[Resource]) -> dict[str, Any]:
    before, after = _findings(base), _findings(spec)

    def count(found: Mapping[Any, Mapping[str, str]]) -> dict[str, int]:
        return {s: sum(1 for f in found.values() if f["severity"] == s) for s in _SEVERITIES}

    return {
        "before": count(before),
        "after": count(after),
        "fixed": [before[k] for k in sorted(set(before) - set(after))],
        "introduced": [after[k] for k in sorted(set(after) - set(before))],
        "remaining": [after[k] for k in sorted(set(after) & set(before))],
    }


def _dependents(resources: Iterable[Resource]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for res in resources:
        for ref in res.references:
            reverse.setdefault(ref, set()).add(res.address)
    return reverse


def _reach(start: str, reverse: Mapping[str, set[str]]) -> list[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        for nxt in reverse.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return sorted(seen)


def _blast_radius(
    base: Mapping[str, Resource],
    spec: Mapping[str, Resource],
    modified: list[str],
    destroyed: list[str],
) -> dict[str, list[str]]:
    in_spec, in_base = _dependents(spec.values()), _dependents(base.values())
    out = {a: _reach(a, in_spec) for a in modified}
    out.update({a: _reach(a, in_base) for a in destroyed})
    return dict(sorted(out.items()))


def _cost(base: list[Resource], spec: list[Resource], region: str) -> dict[str, Any]:
    try:
        before, after = estimate(base, region), estimate(spec, region)
    except UnknownRegion as exc:
        return {"available": False, "reason": str(exc)}
    return {
        "available": True,
        "delta_usd": round(after.total_usd - before.total_usd, 2),
        "baseline": before.to_dict(),
        "spec": after.to_dict(),
        "note": "On-demand list price, 730 hours a month. An estimate of the priced part of the "
        "spec, not a bill; the lists below name what it leaves out.",
    }


def load_plan(store_root: Path, plan_id: str) -> dict[str, Any]:
    """A stored plan by id, searched across runs; raises :class:`PlanRefused` if unknown."""
    if len(plan_id) != 16 or any(c not in "0123456789abcdef" for c in plan_id):
        raise PlanRefused(f"not a plan id: {plan_id!r}")
    for path in (store_root / "runs").glob(f"*/plans/{plan_id}/plan.json"):
        plan: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return plan
    raise PlanRefused(f"no stored plan {plan_id} under {store_root}")


def make_plan(
    store_root: Path,
    run: str,
    *,
    backend: str = "local",
    runner: TerraformRunner | None = None,
) -> dict[str, Any]:
    """Plan the spec stored for ``run``; raises :class:`PlanRefused` with the reason."""
    if backend not in BACKENDS:
        raise PlanRefused(f"unknown backend {backend!r}; expected one of {BACKENDS}")
    run_dir = resolve_run(store_root, run)
    summary = _read(run_dir / "summary.json") or {}
    mode = summary.get("mode", "review")
    _refuse_unless_clean(summary)

    spec_doc = _read(run_dir / "patched_spec.tf.json")
    if spec_doc is None:
        raise PlanRefused("the run has no stored spec to plan")
    if mode == "design":
        base_doc: dict[str, Any] = {"resource": {}}
        baseline_kind = "empty"
    else:
        observed = _read(run_dir / "observed_spec.tf.json")
        if observed is None:
            raise PlanRefused(
                "this run predates stored observed specs, so there is nothing to diff against; "
                "re-run the review"
            )
        base_doc, baseline_kind = observed, "observed"
    if backend == "terraform" and mode != "design":
        raise PlanRefused(
            "the Terraform backend plans a deployment from empty state; a remediation of an "
            "existing account needs that account's state, which this build does not read"
        )

    spec_resources = resources_from_terraform_json(spec_doc)
    base_resources = resources_from_terraform_json(base_doc)
    spec = {r.address: r for r in spec_resources}
    base = {r.address: r for r in base_resources}
    creates, destroys, modifies = _diff(base, spec)
    region = spec_doc.get("provider", {}).get("aws", {}).get("region", "")

    terraform: dict[str, Any] | None = None
    if backend == "terraform":
        terraform = _terraform_section(store_root, spec_doc, runner)

    spec_hash = document_hash(spec_doc)
    baseline_hash = document_hash(base_doc)
    identity: dict[str, Any] = {
        "spec_hash": spec_hash,
        "baseline_hash": baseline_hash,
        "backend": backend,
    }
    if terraform:
        identity["overlay"] = terraform["overlay"]
    plan_id = canonical_hash(identity)[:16]

    existing = run_dir / "plans" / plan_id / "plan.json"
    if existing.exists():
        stored: dict[str, Any] = json.loads(existing.read_text(encoding="utf-8"))
        return stored

    plan: dict[str, Any] = {
        "plan_id": plan_id,
        "run_prefix": run_dir.name,
        "mode": mode,
        "backend": backend,
        "baseline_kind": baseline_kind,
        "region": region,
        "spec_hash": spec_hash,
        "baseline_hash": baseline_hash,
        "creates": creates,
        "destroys": destroys,
        "modifies": modifies,
        "coverage": _coverage(base_resources, spec_resources),
        "blast_radius": _blast_radius(base, spec, [m["address"] for m in modifies], destroys),
        "cost": _cost(list(base_resources), list(spec_resources), region),
        "terraform": terraform,
    }
    LocalArtifactStore(store_root).put(
        f"runs/{run_dir.name}/plans/{plan_id}/plan.json", to_json(plan)
    )
    append_event(store_root, run_dir.name, "planned", plan_id=plan_id, backend=backend)
    return plan


def _terraform_section(
    store_root: Path, spec_doc: Mapping[str, Any], runner: TerraformRunner | None
) -> dict[str, Any]:
    if runner is None:
        if not terraform_available():
            raise PlanRefused("terraform is not installed or not on PATH")
        runner = SubprocessRunner()
    workdir = (
        store_root / "tf" / document_hash(terraform_document(spec_doc, offline=True).document)[:16]
    )
    try:
        result = plan_document(
            spec_doc, workdir, runner, plugin_cache=store_root / "tf" / ".plugin-cache"
        )
    except TerraformError as exc:
        raise PlanRefused(str(exc)) from exc
    return {
        "version": result.version,
        "validated": True,
        "offline": True,
        "creates": list(result.creates),
        "overlay": list(result.overlay),
        "caveats": list(result.caveats),
        "document_hash": result.document_hash,
        "workdir": str(workdir),
    }
