"""``kgcr plan``: readable output, JSON on request, and exit codes that tell a refusal from a
mistyped run id."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kgcr.cli import main
from tests.plan.test_plan_local import _run


def test_plan_prints_the_diff_and_names_what_the_cost_leaves_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prefix = _run(tmp_path, mode="design")
    assert main(["plan", "--spec", prefix, "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "create 3  modify 0  destroy 0" in out and "+ aws_instance.x" in out
    assert "cost delta: +16.64 USD a month" in out
    assert "no price researched for aws_subnet (aws_subnet.a)" in out


def test_plan_json_is_the_stored_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    prefix = _run(tmp_path, mode="design")
    assert main(["plan", "--spec", prefix, "--out", str(tmp_path), "--json"]) == 0
    plan = json.loads(capsys.readouterr().out)
    stored = json.loads(
        (tmp_path / "runs" / prefix / "plans" / plan["plan_id"] / "plan.json").read_text("utf-8")
    )
    assert plan == stored


def test_a_refused_run_exits_1_with_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    loop = {"status": "CONTESTED", "reason": "NON_CONVERGENT", "passes": [{"findings": []}]}
    prefix = _run(tmp_path, mode="design", loop=loop)
    assert main(["plan", "--spec", prefix, "--out", str(tmp_path)]) == 1
    assert "refused" in capsys.readouterr().err


def test_an_unknown_or_hostile_run_id_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for bad in ("ffffffffffffffff", "../outside"):
        assert main(["plan", "--spec", bad, "--out", str(tmp_path)]) == 2
        assert "kgcr plan:" in capsys.readouterr().err
