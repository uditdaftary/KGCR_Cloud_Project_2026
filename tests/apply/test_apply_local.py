"""The simulated apply enforces INV-3 and leaves a recorded partial state on failure."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kgcr.apply import ApplyRefused
from kgcr.apply.local import apply_local
from kgcr.cli import main
from kgcr.orchestration.lifecycle import read_events
from kgcr.plan.local import make_plan
from tests.plan.test_plan_local import SPEC, _run


def _planned(root: Path, **kwargs: object) -> tuple[str, str]:
    prefix = _run(root, **kwargs)  # type: ignore[arg-type]
    return prefix, make_plan(root, prefix)["plan_id"]


def test_a_design_apply_creates_everything_and_records_it(tmp_path: Path) -> None:
    prefix, plan_id = _planned(tmp_path, mode="design")
    record = apply_local(tmp_path, plan_id)
    assert record["status"] == "applied" and record["simulated"] is True
    assert [s["status"] for s in record["steps"]] == ["done"] * 3
    base = tmp_path / "runs" / prefix / "applied" / plan_id
    state = json.loads((base / "state.json").read_text(encoding="utf-8"))
    assert state["resources"] == ["aws_instance.x", "aws_subnet.a", "aws_vpc.main"]
    assert [e["event"] for e in read_events(tmp_path / "runs" / prefix)] == [
        "planned",
        "apply_started",
        "applied",
    ]


def test_a_review_apply_keeps_what_was_there_and_modifies_it(tmp_path: Path) -> None:
    observed = copy.deepcopy(SPEC)
    observed["resource"]["aws_vpc"]["main"]["cidr_block"] = "10.9.0.0/16"
    prefix, plan_id = _planned(tmp_path, observed=observed)
    record = apply_local(tmp_path, plan_id)
    assert [(s["action"], s["address"]) for s in record["steps"]] == [("modify", "aws_vpc.main")]
    state = json.loads(
        (tmp_path / "runs" / prefix / "applied" / plan_id / "state.json").read_text("utf-8")
    )
    assert state["resources"] == ["aws_instance.x", "aws_subnet.a", "aws_vpc.main"]


def test_a_plan_is_applied_once(tmp_path: Path) -> None:
    _, plan_id = _planned(tmp_path, mode="design")
    apply_local(tmp_path, plan_id)
    with pytest.raises(ApplyRefused, match="already applied"):
        apply_local(tmp_path, plan_id)


@pytest.mark.parametrize("plan_id", ["f" * 16, "../../x", "", "xyz"])
def test_no_apply_without_a_stored_plan(tmp_path: Path, plan_id: str) -> None:
    _planned(tmp_path, mode="design")
    with pytest.raises(ApplyRefused, match="INV-3"):
        apply_local(tmp_path, plan_id)


def test_a_spec_changed_after_planning_is_refused(tmp_path: Path) -> None:
    prefix, plan_id = _planned(tmp_path, mode="design")
    path = tmp_path / "runs" / prefix / "patched_spec.tf.json"
    tampered = copy.deepcopy(SPEC)
    tampered["resource"]["aws_instance"]["x"]["instance_type"] = "m5.2xlarge"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ApplyRefused, match="changed after it was planned"):
        apply_local(tmp_path, plan_id)
    assert not (tmp_path / "runs" / prefix / "applied").exists()


def test_a_failure_leaves_a_recorded_partial_state_and_can_be_retried(tmp_path: Path) -> None:
    prefix, plan_id = _planned(tmp_path, mode="design")
    failed = apply_local(tmp_path, plan_id, fail_after=1)
    assert failed["status"] == "failed" and "simulated failure" in failed["error"]
    assert [s["status"] for s in failed["steps"]] == ["done", "failed", "not_run"]
    state = json.loads(
        (tmp_path / "runs" / prefix / "applied" / plan_id / "state.json").read_text("utf-8")
    )
    assert state["resources"] == [failed["steps"][0]["address"]]
    retried = apply_local(tmp_path, plan_id)
    assert retried["status"] == "applied"
    events = [e["event"] for e in read_events(tmp_path / "runs" / prefix)]
    assert events == ["planned", "apply_started", "apply_failed", "apply_started", "applied"]


def test_cli_apply_runs_once_then_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, plan_id = _planned(tmp_path, mode="design")
    assert main(["apply", "--plan", plan_id, "--out", str(tmp_path)]) == 0
    assert "applied (local, simulated)" in capsys.readouterr().out
    assert main(["apply", "--plan", plan_id, "--out", str(tmp_path)]) == 1
    assert "refused" in capsys.readouterr().err


def test_cli_terraform_apply_is_off_unless_switched_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KGCR_APPLY_ENABLED", raising=False)
    assert (
        main(["apply", "--plan", "0" * 16, "--backend", "terraform", "--out", str(tmp_path)]) == 1
    )
    assert "switched off" in capsys.readouterr().err
