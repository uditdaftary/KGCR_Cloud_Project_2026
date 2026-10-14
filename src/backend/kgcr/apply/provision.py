"""The only module that can reach AWS with write credentials (INV-5; FD-01 S10, FD-08).

It is authored, unit-tested against fakes, and **never run by this project's build**: there
are no AWS credentials on the build machine. Whoever runs it owns the account, the cost
and the teardown.

Every gate below runs, in this order, *before* any credential is requested or any Terraform
step runs. A refusal here changes nothing.

1. real applies are switched on (``KGCR_APPLY_ENABLED=1``; the dashboard sets it only for an
   admin job in live mode);
2. the plan exists and the stored spec is the one that was planned (INV-3);
3. the plan came from the Terraform backend;
4. the ``terraform`` binary is present;
5. the write role's grant covers every resource type in the plan (``preflight``);
6. the operator typed the plan id;
7. the operator acknowledged that the budget alarms are applied (FD-08 section 6);
8. an ``aws_instance`` has a real image id, not the placeholder;
9. the role, external id and expected account are configured;
10. the plan was not already applied;
11. the account the role assumes into is the expected one.

A saved offline planfile cannot be applied, because it carries the mock provider settings it
was planned with. So the reviewed plan is *re-planned against the live provider* and applied
only if that plan creates exactly what the reviewed one did and nothing else. Anything
different is refused. Rollback is not automated (FD-01 D5): the record carries the state
path and the teardown command, and does not run it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kgcr.apply import ApplyRefused, preflight
from kgcr.apply.local import reviewed_plan
from kgcr.orchestration.aws import LocalArtifactStore
from kgcr.orchestration.common import to_json
from kgcr.orchestration.lifecycle import append_event, read_events
from kgcr.plan.deployable import PLACEHOLDER_AMI, document_hash, terraform_document
from kgcr.plan.terraform_backend import (
    SubprocessRunner,
    TerraformRunner,
    clean_environment,
    terraform_available,
)

__all__ = ["Credentials", "SessionFactory", "apply_terraform", "boto3_session_factory"]

_ROLE_ARN = re.compile(r"^arn:aws[a-z\-]*:iam::\d{12}:role/[\w+=,.@/\-]{1,256}$")
_ACCOUNT = re.compile(r"^\d{12}$")
_AMI = re.compile(r"^ami-[0-9a-f]{8,17}$")


@dataclass(frozen=True, slots=True)
class Credentials:
    """Short-lived assumed-role keys. Never printed, logged or written."""

    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    session_token: str = field(repr=False)


SessionFactory = Callable[[str, str], tuple[Credentials, str]]
"""``(role_arn, external_id) -> (credentials, account id the role assumed into)``."""


def boto3_session_factory(role_arn: str, external_id: str) -> tuple[Credentials, str]:
    """Assume the write role with STS (needs the ``aws`` extra and the caller's own keys)."""
    import boto3

    response = boto3.client("sts").assume_role(
        RoleArn=role_arn,
        RoleSessionName="kgcr-apply",
        ExternalId=external_id,
        DurationSeconds=3600,
    )
    keys = response["Credentials"]
    account = response["AssumedRoleUser"]["Arn"].split(":")[4]
    return (
        Credentials(keys["AccessKeyId"], keys["SecretAccessKey"], keys["SessionToken"]),
        account,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def apply_terraform(
    store_root: Path,
    plan_id: str,
    *,
    confirm: str,
    budgets_acknowledged: bool,
    env: Mapping[str, str],
    runner: TerraformRunner | None = None,
    session_factory: SessionFactory = boto3_session_factory,
) -> dict[str, Any]:
    """Apply a reviewed Terraform-backend plan to AWS; raises :class:`ApplyRefused` first."""
    if env.get("KGCR_APPLY_ENABLED") != "1":
        raise ApplyRefused("real applies are switched off (KGCR_APPLY_ENABLED is not 1)")
    plan, run_dir = reviewed_plan(store_root, plan_id)
    section = plan.get("terraform")
    if plan["backend"] != "terraform" or not section:
        raise ApplyRefused("only a plan made with the Terraform backend can be applied for real")
    if runner is None:
        if not terraform_available():
            raise ApplyRefused("terraform is not installed or not on PATH")
        runner = SubprocessRunner()

    types = {address.split(".", 1)[0] for address in section["creates"]}
    offenders = preflight.check(types, preflight.allowed_services(env))
    if offenders:
        raise ApplyRefused(
            "the write role's grant does not cover: "
            + "; ".join(offenders)
            + ". Widening the role is your decision (provision_services); nothing was attempted."
        )
    if confirm != plan_id:
        raise ApplyRefused("type the plan id exactly to confirm")
    if not budgets_acknowledged:
        raise ApplyRefused("acknowledge that the budget alarms in src/aws/budgets.tf are applied")
    ami = env.get("KGCR_AMI_ID", "")
    needs_ami = any(a.startswith("aws_instance.") for a in section["creates"])
    if needs_ami and (not _AMI.match(ami) or ami == PLACEHOLDER_AMI):
        raise ApplyRefused("set KGCR_AMI_ID to a real image id for the region (aws_instance)")
    role_arn = env.get("KGCR_PROVISION_ROLE_ARN", "")
    external_id = env.get("KGCR_PROVISION_EXTERNAL_ID", "")
    expected_account = env.get("KGCR_APPLY_ACCOUNT_ID", "")
    if not _ROLE_ARN.match(role_arn) or not external_id or not _ACCOUNT.match(expected_account):
        raise ApplyRefused(
            "set KGCR_PROVISION_ROLE_ARN, KGCR_PROVISION_EXTERNAL_ID and KGCR_APPLY_ACCOUNT_ID"
        )
    if any(e["event"] == "applied" and e.get("plan_id") == plan_id for e in read_events(run_dir)):
        raise ApplyRefused(f"plan {plan_id} was already applied")

    spec = json.loads((run_dir / "patched_spec.tf.json").read_text(encoding="utf-8"))
    live = terraform_document(spec, offline=False)
    if document_hash(live.document) != section["document_hash"]:
        raise ApplyRefused("the document Terraform would use differs from the reviewed one")

    credentials, account = session_factory(role_arn, external_id)
    if account != expected_account:
        raise ApplyRefused(
            f"the role assumes into account ending {account[-4:]}, not the expected account "
            f"ending {expected_account[-4:]}"
        )

    workdir = store_root / "tf" / f"{plan_id}-live"
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "main.tf.json").write_text(
        json.dumps(live.document, indent=2, sort_keys=True), encoding="utf-8"
    )
    child = clean_environment(store_root / "tf" / ".plugin-cache")
    child.update(
        {
            "AWS_ACCESS_KEY_ID": credentials.access_key_id,
            "AWS_SECRET_ACCESS_KEY": credentials.secret_access_key,
            "AWS_SESSION_TOKEN": credentials.session_token,
            "AWS_DEFAULT_REGION": str(spec["provider"]["aws"]["region"]),
        }
    )
    child.pop("AWS_EC2_METADATA_DISABLED", None)
    if needs_ami:
        child["TF_VAR_ami_id"] = ami
    secrets = (credentials.access_key_id, credentials.secret_access_key, credentials.session_token)

    def step(name: str, args: list[str]) -> str:
        assert runner is not None
        done = runner.run(args, workdir, child)
        if done.returncode != 0:
            tail = _redact((done.stderr or done.stdout)[-2000:], secrets)
            raise ApplyRefused(f"terraform {name} failed: {tail.strip()}")
        return done.stdout

    prefix = plan["run_prefix"]
    started = _now()
    step("init", ["init", "-input=false", "-no-color"])
    step("plan", ["plan", "-input=false", "-lock=true", "-no-color", "-out=tfplan"])
    shown = json.loads(step("show", ["show", "-json", "tfplan"]))
    changes = [c for c in shown.get("resource_changes", []) if c["change"]["actions"] != ["no-op"]]
    got = sorted(c["address"] for c in changes if c["change"]["actions"] == ["create"])
    if len(got) != len(changes) or got != sorted(section["creates"]):
        raise ApplyRefused(
            "the live plan differs from the reviewed plan; nothing was applied. "
            f"reviewed {len(section['creates'])} creates, live plan has {len(changes)} changes"
        )

    append_event(store_root, prefix, "apply_started", plan_id=plan_id, backend="terraform")
    status, error = "applied", None
    try:
        step("apply", ["apply", "-input=false", "-no-color", "tfplan"])
    except ApplyRefused as exc:
        status, error = "failed", str(exc)
    record: dict[str, Any] = {
        "plan_id": plan_id,
        "run_prefix": prefix,
        "backend": "terraform",
        "simulated": False,
        "status": status,
        "error": error,
        "account_suffix": account[-4:],
        "state_path": str(workdir / "terraform.tfstate"),
        # Shown, never run: tearing down is the operator's decision (FD-01 D5).
        "teardown_command": f"terraform -chdir={workdir} destroy",
        "started_at": started,
        "finished_at": _now(),
    }
    LocalArtifactStore(store_root).put(
        f"runs/{prefix}/applied/{plan_id}/apply.json", to_json(record)
    )
    append_event(
        store_root,
        prefix,
        "applied" if status == "applied" else "apply_failed",
        plan_id=plan_id,
        backend="terraform",
    )
    return record
