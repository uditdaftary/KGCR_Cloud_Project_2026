"""Checkov as a static labelling function over estate ``.tf.json``.

Checkov is invoked as a subprocess (not imported), so this module loads with or
without Checkov installed; only :func:`run_checkov` requires it. The estate is
written as a *resource-only* ``.tf.json`` — Checkov's ``terraform_json`` parser
rejects the ``provider`` block, and only the ``resource`` block is needed for
resource and graph checks.

:func:`parse_checkov_json` is pure and is what the tests exercise against a
committed fixture, so the parsing contract is verified without a live Checkov
run (which is slow and version-fragile).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kgcr.corpus.estate import Estate

__all__ = [
    "CheckovFinding",
    "checkov_available",
    "run_checkov",
    "parse_checkov_json",
    "resource_verdict",
]


@dataclass(frozen=True, slots=True)
class CheckovFinding:
    """One Checkov check result against one resource."""

    check_id: str
    resource: str
    passed: bool


def checkov_available() -> bool:
    """True if Checkov can be invoked in this environment."""
    return importlib.util.find_spec("checkov") is not None


def run_checkov(estate: Estate) -> list[CheckovFinding]:
    """Run Checkov over ``estate`` and return its findings.

    Writes a resource-only ``.tf.json`` to a temp dir and runs Checkov with
    ``--soft-fail`` so a non-zero exit means a real error, not merely that
    checks failed. Raises ``RuntimeError`` if Checkov is absent or emits no
    parseable JSON.
    """
    if not checkov_available():
        raise RuntimeError("checkov is not installed; install the 'labelling' extra")

    with tempfile.TemporaryDirectory() as directory:
        body = {"resource": estate.to_terraform_json()["resource"]}
        Path(directory, "main.tf.json").write_text(json.dumps(body), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "checkov.main",
                "-d",
                directory,
                "-o",
                "json",
                "--compact",
                "--soft-fail",
            ],
            capture_output=True,
            text=True,
        )

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError(
            f"checkov produced no output (rc={proc.returncode}): {proc.stderr[-300:]}"
        )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"checkov output was not JSON: {exc}") from exc
    return parse_checkov_json(data)


def parse_checkov_json(data: Any) -> list[CheckovFinding]:
    """Parse Checkov's JSON output into findings.

    Accepts either a single run object or the list Checkov emits when multiple
    frameworks run. Each result contributes one :class:`CheckovFinding`.
    """
    runs = data if isinstance(data, list) else [data]
    findings: list[CheckovFinding] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        results = run.get("results", {})
        for kind, passed in (("passed_checks", True), ("failed_checks", False)):
            for check in results.get(kind, []):
                findings.append(
                    CheckovFinding(
                        check_id=str(check["check_id"]),
                        resource=str(check["resource"]),
                        passed=passed,
                    )
                )
    return findings


def resource_verdict(findings: list[CheckovFinding], resource: str) -> frozenset[tuple[str, bool]]:
    """The normalised set of ``(check_id, passed)`` for one resource.

    A set (not a list) so the comparison is order-independent — Checkov's output
    ordering is not stable, and the DF-7 contrast compares verdicts for equality.
    """
    return frozenset((f.check_id, f.passed) for f in findings if f.resource == resource)
