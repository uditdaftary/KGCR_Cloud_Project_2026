"""Run the real Terraform binary against a designed spec, offline (FD-01 S9).

The plan runs with mock credentials and every provider call skipped, so it needs no AWS
account and cannot touch one. It proves the document validates and shows what Terraform
would create. It does not prove an apply would succeed (see ``deployable`` for the caveats).

Terraform is reached through a :class:`TerraformRunner` so tests can substitute a fake.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from kgcr.plan.deployable import document_hash, terraform_document

__all__ = [
    "SubprocessRunner",
    "TerraformError",
    "TerraformPlan",
    "TerraformRunner",
    "clean_environment",
    "plan_document",
    "terraform_available",
    "terraform_binary",
]

_WINGET_LINKS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"


class TerraformError(RuntimeError):
    """A Terraform step failed; ``message`` is the tool's own diagnostics, verbatim."""

    def __init__(self, step: str, message: str) -> None:
        self.step = step
        self.message = message
        super().__init__(f"terraform {step} failed: {message}")


class TerraformRunner(Protocol):
    def run(
        self, args: Sequence[str], cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]: ...


def terraform_binary() -> str | None:
    """The terraform executable on PATH, or the per-user winget link if PATH predates it."""
    found = shutil.which("terraform")
    if found:
        return found
    for name in ("terraform.exe", "terraform"):
        candidate = _WINGET_LINKS / name
        if candidate.is_file():
            return str(candidate)
    return None


def terraform_available() -> bool:
    return terraform_binary() is not None


class SubprocessRunner:
    """The real binary, one argument list at a time (never a shell)."""

    def __init__(self, binary: str | None = None, timeout: float = 1800.0) -> None:
        resolved = binary or terraform_binary()
        if resolved is None:
            raise TerraformError("locate", "terraform is not installed or not on PATH")
        self.binary = resolved
        self.timeout = timeout

    def run(
        self, args: Sequence[str], cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.binary, *args],
            cwd=cwd,
            env=dict(env),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )


def clean_environment(plugin_cache: Path) -> dict[str, str]:
    """The inherited environment minus any cloud or model credential, plus mock AWS keys.

    A plan is offline by construction; nothing the operator has exported can leak into it.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AWS_", "GEMINI_", "KGCR_", "TF_VAR_"))
    }
    plugin_cache.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "AWS_ACCESS_KEY_ID": "mock",
            "AWS_SECRET_ACCESS_KEY": "mock",
            "AWS_EC2_METADATA_DISABLED": "true",
            "TF_PLUGIN_CACHE_DIR": str(plugin_cache),
            "TF_IN_AUTOMATION": "1",
            "TF_INPUT": "0",
            "CHECKPOINT_DISABLE": "1",
        }
    )
    return env


@dataclass(frozen=True, slots=True)
class TerraformPlan:
    version: str
    creates: tuple[str, ...]
    overlay: tuple[str, ...]
    caveats: tuple[str, ...]
    plan_json: dict[str, Any]
    workdir: Path
    document_hash: str


def _step(
    runner: TerraformRunner, step: str, args: Sequence[str], cwd: Path, env: Mapping[str, str]
) -> str:
    done = runner.run(args, cwd, env)
    if done.returncode != 0:
        raise TerraformError(step, _diagnostics(done))
    return done.stdout


def _diagnostics(done: subprocess.CompletedProcess[str]) -> str:
    """Terraform's own error text: the JSON diagnostics when present, else stderr."""
    try:
        parsed = json.loads(done.stdout)
        found = [
            f"{d.get('summary', '')}: {d.get('detail', '')}".strip(": ")
            for d in parsed.get("diagnostics", [])
            if d.get("severity") == "error"
        ]
        if found:
            return "; ".join(found)
    except ValueError:
        pass
    return (done.stderr or done.stdout).strip() or f"exit {done.returncode}"


def plan_document(
    spec: Mapping[str, Any], workdir: Path, runner: TerraformRunner, *, plugin_cache: Path
) -> TerraformPlan:
    """init, validate and an offline plan of a spec document; raises :class:`TerraformError`."""
    workdir.mkdir(parents=True, exist_ok=True)
    overlaid = terraform_document(spec, offline=True)
    (workdir / "main.tf.json").write_text(
        json.dumps(overlaid.document, indent=2, sort_keys=True), encoding="utf-8"
    )
    env = clean_environment(plugin_cache)
    version = json.loads(_step(runner, "version", ["version", "-json"], workdir, env))
    _step(runner, "init", ["init", "-backend=false", "-input=false", "-no-color"], workdir, env)
    _step(runner, "validate", ["validate", "-json", "-no-color"], workdir, env)
    _step(
        runner,
        "plan",
        ["plan", "-input=false", "-refresh=false", "-lock=false", "-no-color", "-out=tfplan"],
        workdir,
        env,
    )
    shown = json.loads(_step(runner, "show", ["show", "-json", "tfplan"], workdir, env))
    creates = sorted(
        c["address"]
        for c in shown.get("resource_changes", [])
        if c.get("change", {}).get("actions") == ["create"]
    )
    return TerraformPlan(
        version=str(version.get("terraform_version", "")),
        creates=tuple(creates),
        overlay=overlaid.overlay,
        caveats=overlaid.caveats,
        plan_json=shown,
        workdir=workdir,
        document_hash=document_hash(overlaid.document),
    )
