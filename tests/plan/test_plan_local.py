"""A plan is an immutable diff of a stored run's spec, and some runs are never planned."""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from kgcr.orchestration.lifecycle import read_events
from kgcr.orchestration.runstore import RunNotFound
from kgcr.plan.local import PlanRefused, load_plan, make_plan

PREFIX = "abcdef0123456789"
REGION = {"aws": {"region": "eu-west-1"}}
SPEC: dict[str, Any] = {
    "provider": REGION,
    "resource": {
        "aws_vpc": {"main": {"cidr_block": "10.0.0.0/16"}},
        "aws_subnet": {"a": {"vpc_id": "${aws_vpc.main.id}", "cidr_block": "10.0.1.0/24"}},
        "aws_instance": {"x": {"instance_type": "t3.small", "subnet_id": "${aws_subnet.a.id}"}},
    },
}
CLEAN_LOOP = {"status": "CONVERGED", "reason": "CLEAN", "passes": [{"findings": []}]}


def _run(
    root: Path,
    *,
    mode: str = "review",
    spec: Mapping[str, Any] = SPEC,
    observed: Mapping[str, Any] | None = None,
    loop: Mapping[str, Any] = CLEAN_LOOP,
    prefix: str = PREFIX,
) -> str:
    run_dir = root / "runs" / prefix
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps({"mode": mode, "loop": loop}), encoding="utf-8"
    )
    (run_dir / "patched_spec.tf.json").write_text(json.dumps(spec), encoding="utf-8")
    if observed is not None:
        (run_dir / "observed_spec.tf.json").write_text(json.dumps(observed), encoding="utf-8")
    return prefix


def test_a_design_plan_is_all_creates_with_a_priced_delta(tmp_path: Path) -> None:
    prefix = _run(tmp_path, mode="design")
    plan = make_plan(tmp_path, prefix)
    assert plan["baseline_kind"] == "empty"
    assert plan["creates"] == ["aws_instance.x", "aws_subnet.a", "aws_vpc.main"]
    assert plan["destroys"] == [] and plan["modifies"] == []
    assert plan["cost"]["available"] and plan["cost"]["delta_usd"] == 16.64
    assert any("aws_vpc.main" in n for n in plan["cost"]["spec"]["not_priced"])


def test_a_review_plan_modifies_only_what_changed(tmp_path: Path) -> None:
    observed = copy.deepcopy(SPEC)
    observed["resource"]["aws_vpc"]["main"]["cidr_block"] = "10.9.0.0/16"
    prefix = _run(tmp_path, observed=observed)
    plan = make_plan(tmp_path, prefix)
    assert plan["creates"] == [] and plan["destroys"] == []
    assert plan["modifies"] == [
        {
            "address": "aws_vpc.main",
            "changes": [
                {"attribute": "cidr_block", "before": "10.9.0.0/16", "after": "10.0.0.0/16"}
            ],
        }
    ]
    # Everything that hangs off the modified VPC is in its blast radius, transitively.
    assert plan["blast_radius"] == {"aws_vpc.main": ["aws_instance.x", "aws_subnet.a"]}


def test_a_destroyed_resource_reports_what_depends_on_it(tmp_path: Path) -> None:
    observed = copy.deepcopy(SPEC)
    observed["resource"]["aws_subnet"]["b"] = {
        "vpc_id": "${aws_vpc.main.id}",
        "cidr_block": "10.0.2.0/24",
    }
    observed["resource"]["aws_instance"]["y"] = {
        "instance_type": "t3.small",
        "subnet_id": "${aws_subnet.b.id}",
    }
    prefix = _run(tmp_path, observed=observed)
    plan = make_plan(tmp_path, prefix)
    assert plan["destroys"] == ["aws_instance.y", "aws_subnet.b"]
    assert plan["blast_radius"] == {"aws_instance.y": [], "aws_subnet.b": ["aws_instance.y"]}
    assert plan["cost"]["delta_usd"] == -16.64


def test_coverage_counts_findings_before_and_after(tmp_path: Path) -> None:
    unencrypted = {
        "aws_db_instance": {
            "db": {
                "engine": "postgres",
                "instance_class": "db.t3.small",
                "allocated_storage": 20,
                "storage_encrypted": False,
            }
        }
    }
    encrypted = {
        "aws_db_instance": {
            "db": {**unencrypted["aws_db_instance"]["db"], "storage_encrypted": True}
        }
    }
    prefix = _run(
        tmp_path,
        spec={"provider": REGION, "resource": encrypted},
        observed={"provider": REGION, "resource": unencrypted},
    )
    coverage = make_plan(tmp_path, prefix)["coverage"]
    assert coverage["before"]["CRITICAL"] == 1 and coverage["after"]["CRITICAL"] == 0
    assert [f["address"] for f in coverage["fixed"]] == ["aws_db_instance.db"]
    assert coverage["introduced"] == []


def test_a_contested_run_is_refused(tmp_path: Path) -> None:
    loop = {"status": "CONTESTED", "reason": "OSCILLATING", "passes": [{"findings": []}]}
    prefix = _run(tmp_path, mode="design", loop=loop)
    with pytest.raises(PlanRefused, match="CONTESTED"):
        make_plan(tmp_path, prefix)
    assert not (tmp_path / "runs" / prefix / "plans").exists()


def test_a_run_with_an_open_critical_is_refused_even_if_marked_converged(tmp_path: Path) -> None:
    loop = {
        "status": "CONVERGED",
        "reason": "CLEAN",
        "passes": [{"findings": [{"severity": "CRITICAL"}]}],
    }
    prefix = _run(tmp_path, mode="design", loop=loop)
    with pytest.raises(PlanRefused, match="CRITICAL"):
        make_plan(tmp_path, prefix)


def test_a_review_stored_before_observed_specs_existed_says_to_rerun(tmp_path: Path) -> None:
    prefix = _run(tmp_path)  # no observed_spec.tf.json
    with pytest.raises(PlanRefused, match="re-run the review"):
        make_plan(tmp_path, prefix)


def test_the_terraform_backend_refuses_a_review(tmp_path: Path) -> None:
    prefix = _run(tmp_path, observed=SPEC)
    with pytest.raises(PlanRefused, match="empty state|account's state"):
        make_plan(tmp_path, prefix, backend="terraform")


def test_an_unknown_backend_and_a_hostile_run_id_are_refused(tmp_path: Path) -> None:
    prefix = _run(tmp_path, mode="design")
    with pytest.raises(PlanRefused, match="unknown backend"):
        make_plan(tmp_path, prefix, backend="pulumi")
    for bad in ("../outside", "C:\\x", "ABC", ""):
        with pytest.raises(RunNotFound):
            make_plan(tmp_path, bad)


def test_a_plan_is_idempotent_and_immutable(tmp_path: Path) -> None:
    prefix = _run(tmp_path, mode="design")
    first = make_plan(tmp_path, prefix)
    path = tmp_path / "runs" / prefix / "plans" / first["plan_id"] / "plan.json"
    stored = path.read_bytes()
    second = make_plan(tmp_path, prefix)
    assert second == first and path.read_bytes() == stored
    assert [e["event"] for e in read_events(tmp_path / "runs" / prefix)] == ["planned"]
    assert load_plan(tmp_path, first["plan_id"]) == first


def test_a_changed_spec_is_a_different_plan(tmp_path: Path) -> None:
    other = copy.deepcopy(SPEC)
    other["resource"]["aws_instance"]["x"]["instance_type"] = "m5.large"
    a = make_plan(tmp_path, _run(tmp_path, mode="design"))
    b = make_plan(tmp_path, _run(tmp_path, mode="design", spec=other, prefix="0123456789abcdef"))
    assert a["plan_id"] != b["plan_id"]


@pytest.mark.parametrize("bad", ["", "xyz", "A" * 16, "../../etc/passw", "0" * 15])
def test_load_plan_refuses_anything_but_a_plan_id(tmp_path: Path, bad: str) -> None:
    with pytest.raises(PlanRefused):
        load_plan(tmp_path, bad)


class _FakeTerraform:
    def run(
        self, args: Sequence[str], cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        out = {
            "version": '{"terraform_version": "1.16.5"}',
            "show": json.dumps(
                {
                    "resource_changes": [
                        {"address": "aws_vpc.main", "change": {"actions": ["create"]}}
                    ]
                }
            ),
            "validate": '{"valid": true, "diagnostics": []}',
        }.get(args[0], "")
        return subprocess.CompletedProcess(list(args), 0, out, "")


def test_the_terraform_backend_records_the_overlay_and_changes_the_plan_identity(
    tmp_path: Path,
) -> None:
    prefix = _run(tmp_path, mode="design")
    local = make_plan(tmp_path, prefix)
    tf = make_plan(tmp_path, prefix, backend="terraform", runner=_FakeTerraform())
    assert tf["plan_id"] != local["plan_id"] and tf["backend"] == "terraform"
    assert tf["terraform"]["version"] == "1.16.5" and tf["terraform"]["offline"] is True
    assert tf["terraform"]["creates"] == ["aws_vpc.main"]
    assert tf["terraform"]["overlay"] and tf["terraform"]["document_hash"]
    assert (tmp_path / "tf").is_dir()


def test_the_terraform_backend_without_a_binary_is_refused_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kgcr.plan.local.terraform_available", lambda: False)
    prefix = _run(tmp_path, mode="design")
    with pytest.raises(PlanRefused, match="not installed"):
        make_plan(tmp_path, prefix, backend="terraform")
    assert not (tmp_path / "runs" / prefix / "plans").exists()
