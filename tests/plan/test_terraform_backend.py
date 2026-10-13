"""The Terraform harness runs init, validate, plan and show in order, offline, and reports
the tool's own diagnostics. The real binary is exercised when it is installed."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.design.intake import build_intent
from kgcr.plan.terraform_backend import (
    SubprocessRunner,
    TerraformError,
    clean_environment,
    plan_document,
    terraform_available,
)

ESTATE = render_estate(
    build_intent(
        {
            "archetype": "payments_api",
            "region": "eu-west-1",
            "az_spread": "two_az",
            "network_layout": "public_private",
            "logging": "full",
            "iam_shape": "least_privilege",
            "tagging": "strict",
            "scale": "small",
        }
    ),
    1729,
)
SHOWN = {
    "resource_changes": [
        {"address": "aws_vpc.main", "change": {"actions": ["create"]}},
        {"address": "aws_kms_key.main", "change": {"actions": ["create"]}},
        {"address": "aws_s3_bucket.old", "change": {"actions": ["no-op"]}},
    ]
}


class FakeRunner:
    def __init__(
        self, validate: tuple[int, str] = (0, '{"valid": true, "diagnostics": []}')
    ) -> None:
        self.validate = validate
        self.calls: list[tuple[str, dict[str, str]]] = []

    def run(
        self, args: Sequence[str], cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        verb = args[0]
        self.calls.append((verb, dict(env)))
        if verb == "validate":
            return subprocess.CompletedProcess(list(args), self.validate[0], self.validate[1], "")
        out = {"version": '{"terraform_version": "1.16.5"}', "show": json.dumps(SHOWN)}.get(
            verb, ""
        )
        return subprocess.CompletedProcess(list(args), 0, out, "")


def test_steps_run_in_order_and_the_plan_is_parsed(tmp_path: Path) -> None:
    runner = FakeRunner()
    plan = plan_document(
        ESTATE.to_terraform_json(), tmp_path / "w", runner, plugin_cache=tmp_path / "cache"
    )
    assert [verb for verb, _ in runner.calls] == ["version", "init", "validate", "plan", "show"]
    assert plan.version == "1.16.5"
    assert plan.creates == ("aws_kms_key.main", "aws_vpc.main")  # no-op is not a create
    assert plan.overlay and plan.caveats
    doc = json.loads((tmp_path / "w" / "main.tf.json").read_text(encoding="utf-8"))
    assert doc["provider"]["aws"]["skip_credentials_validation"] is True


def test_a_failed_validate_carries_terraforms_own_message_and_stops(tmp_path: Path) -> None:
    diagnostics = {
        "diagnostics": [
            {
                "severity": "error",
                "summary": "Insufficient rule blocks",
                "detail": "At least 1 rule",
            }
        ]
    }
    runner = FakeRunner(validate=(1, json.dumps(diagnostics)))
    with pytest.raises(TerraformError) as exc:
        plan_document(
            ESTATE.to_terraform_json(), tmp_path / "w", runner, plugin_cache=tmp_path / "c"
        )
    assert exc.value.step == "validate" and "Insufficient rule blocks" in exc.value.message
    assert [verb for verb, _ in runner.calls] == ["version", "init", "validate"]  # never planned


def test_real_credentials_never_reach_terraform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "do-not-leak")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "do-not-leak")
    monkeypatch.setenv("GEMINI_API_KEY", "do-not-leak")
    monkeypatch.setenv("TF_VAR_ami_id", "ami-real")
    env = clean_environment(tmp_path / "cache")
    assert env["AWS_SECRET_ACCESS_KEY"] == "mock" and env["AWS_ACCESS_KEY_ID"] == "mock"
    assert "AWS_SESSION_TOKEN" not in env and "GEMINI_API_KEY" not in env
    assert "TF_VAR_ami_id" not in env and env["TF_IN_AUTOMATION"] == "1"
    assert "do-not-leak" not in json.dumps(env)


def test_a_missing_binary_is_reported_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kgcr.plan.terraform_backend.terraform_binary", lambda: None)
    with pytest.raises(TerraformError, match="not installed"):
        SubprocessRunner()


@pytest.mark.skipif(not terraform_available(), reason="terraform is not installed")
def test_the_real_binary_validates_and_plans_a_generated_estate_offline(tmp_path: Path) -> None:
    # Observed 2026-10-13 with Terraform 1.16.5: the raw estate fails `validate` (a load
    # balancer with no subnets, an encryption configuration with no rule). With the overlay
    # the document validates and plans offline.
    cache = Path(__file__).resolve().parents[2] / "runs-local" / "tf" / ".plugin-cache"
    plan = plan_document(
        ESTATE.to_terraform_json(), tmp_path / "w", SubprocessRunner(), plugin_cache=cache
    )
    assert plan.version.startswith("1.")
    assert "aws_db_instance.cardholder" in plan.creates and "aws_lb.api" in plan.creates
    assert "aws_db_subnet_group.kgcr" in plan.creates  # added by the overlay, and reported
