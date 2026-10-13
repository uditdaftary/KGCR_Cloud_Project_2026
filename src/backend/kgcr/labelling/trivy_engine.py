"""Trivy (tfsec's successor) as a second static labelling function over estate ``.tf.json``.

Mirrors :mod:`kgcr.labelling.checkov_engine`: invoked as a subprocess, over a resource-only
``.tf.json``, with a pure parser that the tests exercise against a committed fixture so the
contract is verified without a live scan. Only the failures Trivy prints are returned; Trivy
does not list passes by default, so a resource with no finding is "not flagged", which is how
agreement treats it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kgcr.corpus.estate import Estate

__all__ = ["TrivyFinding", "parse_trivy_json", "run_trivy", "trivy_available", "trivy_binary"]

_WINGET_LINKS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"


@dataclass(frozen=True, slots=True)
class TrivyFinding:
    """One Trivy misconfiguration against one resource."""

    check_id: str  # e.g. AWS-0080
    resource: str  # e.g. aws_db_instance.cardholder
    title: str


def trivy_binary() -> str | None:
    """trivy on PATH, or the per-user winget link if PATH predates the install."""
    found = shutil.which("trivy")
    if found:
        return found
    for name in ("trivy.exe", "trivy"):
        candidate = _WINGET_LINKS / name
        if candidate.is_file():
            return str(candidate)
    return None


def trivy_available() -> bool:
    return trivy_binary() is not None


def parse_trivy_json(data: Any) -> list[TrivyFinding]:
    """Trivy's ``config --format json`` output into findings (failures only)."""
    findings: list[TrivyFinding] = []
    if not isinstance(data, dict):
        return findings
    for result in data.get("Results") or []:
        for m in result.get("Misconfigurations") or []:
            if m.get("Status") != "FAIL":
                continue
            resource = (m.get("CauseMetadata") or {}).get("Resource")
            if resource:
                findings.append(TrivyFinding(str(m["ID"]), str(resource), str(m.get("Title", ""))))
    return findings


def run_trivy(estate: Estate) -> list[TrivyFinding]:
    """Scan ``estate`` with Trivy; raises ``RuntimeError`` if it is absent or fails."""
    binary = trivy_binary()
    if binary is None:
        raise RuntimeError("trivy is not installed or not on PATH")
    with tempfile.TemporaryDirectory() as directory:
        body = {"resource": estate.to_terraform_json()["resource"]}
        Path(directory, "main.tf.json").write_text(json.dumps(body), encoding="utf-8")
        done = subprocess.run(
            [binary, "config", "--format", "json", "--quiet", directory],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    if done.returncode != 0 or not done.stdout.strip():
        raise RuntimeError(f"trivy failed (rc={done.returncode}): {done.stderr[-300:]}")
    try:
        return parse_trivy_json(json.loads(done.stdout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"trivy output was not JSON: {exc}") from exc
