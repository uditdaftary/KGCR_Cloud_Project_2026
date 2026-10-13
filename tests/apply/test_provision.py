"""The gated Terraform apply. Every gate refuses before a credential is requested or a
Terraform step runs; with all gates passed it applies exactly what was reviewed.

Everything here runs against fakes. The real path has never been run: there are no AWS
credentials on the build machine.
"""

from __future__ import annotations

import ast
import copy
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from kgcr.apply import ApplyRefused
from kgcr.apply.provision import Credentials, apply_terraform
from kgcr.orchestration.lifecycle import read_events
from kgcr.plan.deployable import PLACEHOLDER_AMI
from kgcr.plan.local import make_plan
from tests.plan.test_plan_local import SPEC, _run

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = "123456789012"
SECRETS = ("AKIAFAKEKEY", "FAKESECRETVALUE", "FAKETOKENVALUE")
ENV = {
    "KGCR_APPLY_ENABLED": "1",
    "KGCR_PROVISION_ROLE_ARN": f"arn:aws:iam::{ACCOUNT}:role/KGCRProvisionApply",
    "KGCR_PROVISION_EXTERNAL_ID": "an-external-id",
    "KGCR_APPLY_ACCOUNT_ID": ACCOUNT,
    "KGCR_AMI_ID": "ami-0abcdef1234567890",
}
CREATES = ["aws_instance.x", "aws_subnet.a", "aws_vpc.main"]


class Tf:
    """A fake Terraform: records every call; `show` reports the creates it was given."""

    def __init__(self, creates: Sequence[str] = CREATES, fail_apply: bool = False) -> None:
        self.creates = list(creates)
        self.fail_apply = fail_apply
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    @property
    def verbs(self) -> list[str]:
        return [args[0] for args, _ in self.calls]

    def run(
        self, args: Sequence[str], cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), dict(env)))
        verb = args[0]
        if verb == "apply" and self.fail_apply:
            return subprocess.CompletedProcess(list(args), 1, "", f"boom {SECRETS[1]} boom")
        out = {
            "version": '{"terraform_version": "1.16.5"}',
            "validate": '{"valid": true, "diagnostics": []}',
            "show": json.dumps(
                {
                    "resource_changes": [
                        {"address": a, "change": {"actions": ["create"]}} for a in self.creates
                    ]
                }
            ),
        }.get(verb, "")
        return subprocess.CompletedProcess(list(args), 0, out, "")


class Sessions:
    def __init__(self, account: str = ACCOUNT) -> None:
        self.account = account
        self.calls = 0

    def __call__(self, role_arn: str, external_id: str) -> tuple[Credentials, str]:
        self.calls += 1
        return Credentials(*SECRETS), self.account


def _plan(root: Path, spec: dict[str, Any] = SPEC, creates: Sequence[str] = CREATES) -> str:
    prefix = _run(root, mode="design", spec=spec)
    return str(make_plan(root, prefix, backend="terraform", runner=Tf(creates))["plan_id"])


def _apply(
    root: Path,
    plan_id: str,
    *,
    runner: Tf | None = None,
    sessions: Sessions | None = None,
    env: Mapping[str, str] = ENV,
    confirm: str | None = None,
    budgets: bool = True,
) -> dict[str, Any]:
    return apply_terraform(
        root,
        plan_id,
        confirm=plan_id if confirm is None else confirm,
        budgets_acknowledged=budgets,
        env=env,
        runner=runner or Tf(),
        session_factory=sessions or Sessions(),
    )


def _without(key: str) -> dict[str, str]:
    return {k: v for k, v in ENV.items() if k != key}


GATES: list[tuple[str, dict[str, Any], str]] = [
    ("switched off", {"env": _without("KGCR_APPLY_ENABLED")}, "switched off"),
    ("wrong confirmation", {"confirm": "0" * 16}, "type the plan id"),
    ("budgets not acknowledged", {"budgets": False}, "budget alarms"),
    ("no image id", {"env": _without("KGCR_AMI_ID")}, "KGCR_AMI_ID"),
    ("placeholder image id", {"env": {**ENV, "KGCR_AMI_ID": PLACEHOLDER_AMI}}, "KGCR_AMI_ID"),
    ("no role arn", {"env": _without("KGCR_PROVISION_ROLE_ARN")}, "KGCR_PROVISION_ROLE_ARN"),
    ("malformed role arn", {"env": {**ENV, "KGCR_PROVISION_ROLE_ARN": "arn:nope"}}, "ROLE_ARN"),
    ("no external id", {"env": _without("KGCR_PROVISION_EXTERNAL_ID")}, "EXTERNAL_ID"),
    ("no allow-listed account", {"env": _without("KGCR_APPLY_ACCOUNT_ID")}, "APPLY_ACCOUNT_ID"),
]


@pytest.mark.parametrize(("label", "kwargs", "message"), GATES, ids=[g[0] for g in GATES])
def test_each_gate_refuses_before_any_credential_or_terraform_step(
    tmp_path: Path, label: str, kwargs: dict[str, Any], message: str
) -> None:
    plan_id = _plan(tmp_path)
    runner, sessions = Tf(), Sessions()
    with pytest.raises(ApplyRefused, match=message):
        _apply(tmp_path, plan_id, runner=runner, sessions=sessions, **kwargs)
    assert runner.calls == [] and sessions.calls == 0, label
    assert not list((tmp_path / "runs").glob("*/applied")), label


def test_a_plan_the_role_cannot_carry_is_refused_naming_the_service(tmp_path: Path) -> None:
    spec = copy.deepcopy(SPEC)
    spec["resource"]["aws_db_instance"] = {
        "db": {"engine": "postgres", "instance_class": "db.t3.small"}
    }
    plan_id = _plan(tmp_path, spec, [*CREATES, "aws_db_instance.db"])
    runner, sessions = Tf(), Sessions()
    with pytest.raises(ApplyRefused, match=r"aws_db_instance \(needs rds\)"):
        _apply(tmp_path, plan_id, runner=runner, sessions=sessions)
    assert runner.calls == [] and sessions.calls == 0
    # The widening is the operator's declared decision, not this code's.
    runner = Tf(creates=[*CREATES, "aws_db_instance.db"])
    widened = {**ENV, "KGCR_PROVISION_SERVICES": "ec2,s3,rds"}
    assert _apply(tmp_path, plan_id, runner=runner, env=widened)["status"] == "applied"


def test_a_local_backend_plan_cannot_be_applied_for_real(tmp_path: Path) -> None:
    prefix = _run(tmp_path, mode="design")
    local_plan = make_plan(tmp_path, prefix)["plan_id"]
    with pytest.raises(ApplyRefused, match="Terraform backend"):
        _apply(tmp_path, local_plan)


def test_no_apply_without_a_plan_or_after_the_spec_moved(tmp_path: Path) -> None:
    with pytest.raises(ApplyRefused, match="INV-3"):
        _apply(tmp_path, "f" * 16, confirm="f" * 16)
    plan_id = _plan(tmp_path)
    prefix = next((tmp_path / "runs").iterdir()).name
    moved = copy.deepcopy(SPEC)
    moved["resource"]["aws_instance"]["x"]["instance_type"] = "m5.2xlarge"
    (tmp_path / "runs" / prefix / "patched_spec.tf.json").write_text(json.dumps(moved), "utf-8")
    runner = Tf()
    with pytest.raises(ApplyRefused, match="changed after it was planned"):
        _apply(tmp_path, plan_id, runner=runner)
    assert runner.calls == []


def test_a_missing_binary_refuses_when_no_runner_is_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_id = _plan(tmp_path)
    monkeypatch.setattr("kgcr.apply.provision.terraform_available", lambda: False)
    with pytest.raises(ApplyRefused, match="not installed"):
        apply_terraform(
            tmp_path,
            plan_id,
            confirm=plan_id,
            budgets_acknowledged=True,
            env=ENV,
            session_factory=Sessions(),
        )


def test_the_wrong_account_is_refused_after_assuming_but_before_terraform(tmp_path: Path) -> None:
    plan_id = _plan(tmp_path)
    runner, sessions = Tf(), Sessions(account="999999999999")
    with pytest.raises(ApplyRefused, match="not the expected account"):
        _apply(tmp_path, plan_id, runner=runner, sessions=sessions)
    assert sessions.calls == 1 and runner.calls == []


def test_a_drifted_document_is_refused_before_any_credential(tmp_path: Path) -> None:
    plan_id = _plan(tmp_path)
    plan_path = next((tmp_path / "runs").glob("*/plans/*/plan.json"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["terraform"]["document_hash"] = "0" * 64
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    runner, sessions = Tf(), Sessions()
    with pytest.raises(ApplyRefused, match="differs from the reviewed one"):
        _apply(tmp_path, plan_id, runner=runner, sessions=sessions)
    assert runner.calls == [] and sessions.calls == 0


def test_a_live_plan_that_differs_from_the_reviewed_one_is_never_applied(tmp_path: Path) -> None:
    plan_id = _plan(tmp_path)
    runner = Tf(creates=[*CREATES, "aws_s3_bucket.surprise"])
    with pytest.raises(ApplyRefused, match="live plan differs"):
        _apply(tmp_path, plan_id, runner=runner)
    assert "apply" not in runner.verbs and runner.verbs == ["init", "plan", "show"]


def test_with_every_gate_passed_it_applies_the_saved_plan_and_keeps_secrets_out(
    tmp_path: Path,
) -> None:
    plan_id = _plan(tmp_path)
    prefix = next((tmp_path / "runs").iterdir()).name
    runner, sessions = Tf(), Sessions()
    record = _apply(tmp_path, plan_id, runner=runner, sessions=sessions)
    assert record["status"] == "applied" and record["simulated"] is False
    assert runner.verbs == ["init", "plan", "show", "apply"]
    assert runner.calls[-1][0] == ["apply", "-input=false", "-no-color", "tfplan"]
    env = runner.calls[-1][1]
    assert env["AWS_ACCESS_KEY_ID"] == SECRETS[0] and env["TF_VAR_ami_id"] == ENV["KGCR_AMI_ID"]
    assert "destroy" not in runner.verbs  # the teardown is shown, never run
    assert record["teardown_command"].startswith("terraform -chdir=")
    assert record["teardown_command"].endswith("destroy")
    assert record["state_path"].endswith("terraform.tfstate")
    stored = (tmp_path / "runs" / prefix / "applied" / plan_id / "apply.json").read_text("utf-8")
    assert not any(secret in stored for secret in SECRETS)
    assert not any(secret in repr(Credentials(*SECRETS)) for secret in SECRETS)
    events = [e["event"] for e in read_events(tmp_path / "runs" / prefix)]
    assert events == ["planned", "apply_started", "applied"]


def test_a_failed_apply_is_recorded_redacted_and_not_retried_silently(tmp_path: Path) -> None:
    plan_id = _plan(tmp_path)
    prefix = next((tmp_path / "runs").iterdir()).name
    record = _apply(tmp_path, plan_id, runner=Tf(fail_apply=True))
    assert record["status"] == "failed"
    assert SECRETS[1] not in json.dumps(record) and "[redacted]" in record["error"]
    assert read_events(tmp_path / "runs" / prefix)[-1]["event"] == "apply_failed"


def test_a_plan_is_applied_for_real_only_once(tmp_path: Path) -> None:
    plan_id = _plan(tmp_path)
    _apply(tmp_path, plan_id)
    runner = Tf()
    with pytest.raises(ApplyRefused, match="already applied"):
        _apply(tmp_path, plan_id, runner=runner)
    assert runner.calls == []


def test_only_the_cli_and_the_apply_package_import_the_write_path() -> None:
    # INV-5: one module builds a write session, and nothing else reaches for it.
    importers: set[str] = set()
    for path in (ROOT / "src" / "backend" / "kgcr").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            if "kgcr.apply.provision" in names:
                importers.add(path.relative_to(ROOT / "src" / "backend" / "kgcr").as_posix())
    assert importers <= {"cli.py"}, importers
    assert "cli.py" in importers


def test_the_write_path_is_the_only_module_that_assumes_a_role() -> None:
    offenders = [
        p.name
        for p in (ROOT / "src" / "backend" / "kgcr").rglob("*.py")
        if ".assume_role(" in p.read_text(encoding="utf-8") and p.name != "provision.py"
    ]
    assert offenders == []
