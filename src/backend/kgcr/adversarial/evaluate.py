"""How the rule floor fares on configurations someone else wrote (FD-05 4D).

TerraGoat and CloudGoat are vulnerable by design, so a finding is the expected outcome, and
the repositories carry no per-resource labels. Checkov, an independent implementation, is
therefore the comparison. For each defect family the rule floor covers, over the resources
of the types it can see, this counts how often the rule floor and Checkov agree.

What this does not show, stated plainly:

* the rule floor has seven rules, so it is silent on everything outside those families.
  ``coverage`` reports how much of what Checkov fails falls outside them;
* the family map below is this project's own mapping of Checkov ids onto the rule floor's
  rules, not an official one;
* the rule floor reads literal values, so an unresolved expression is counted separately as a
  blind spot (it is not a pass, and not a finding);
* agreement with Checkov is not correctness: both can be wrong the same way.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from kgcr.adversarial.hcl import ParsedDirectory
from kgcr.corpus.resources import Resource
from kgcr.defects.detectors import resource_findings

__all__ = [
    "FAMILIES",
    "CheckovResult",
    "Family",
    "evaluate",
    "parse_results",
    "run_checkov_directory",
]


@dataclass(frozen=True, slots=True)
class Family:
    key: str
    label: str
    types: frozenset[str]
    ours: frozenset[str]  # rule ids the rule floor raises for this family
    checkov: frozenset[str]  # Checkov ids treated as the same defect (this project's mapping)
    attribute: str  # the attribute whose unresolved expression blinds the rule


FAMILIES: tuple[Family, ...] = (
    Family(
        "open_ingress",
        "DF-1 security group open to 0.0.0.0/0",
        frozenset({"aws_security_group"}),
        frozenset({"CKV_AWS_260"}),
        # Checkov splits this by port; the rule floor flags any port, so it can flag more.
        frozenset({"CKV_AWS_260", "CKV_AWS_24", "CKV_AWS_25", "CKV_AWS_277"}),
        "ingress",
    ),
    Family(
        "public_database",
        "DF-1 database publicly accessible",
        frozenset({"aws_db_instance"}),
        frozenset({"CKV_AWS_17"}),
        frozenset({"CKV_AWS_17"}),
        "publicly_accessible",
    ),
    Family(
        "public_bucket_acl",
        "DF-1 bucket with a public ACL",
        frozenset({"aws_s3_bucket"}),
        frozenset({"CKV_AWS_20"}),
        frozenset({"CKV_AWS_20", "CKV_AWS_57"}),
        "acl",
    ),
    Family(
        "unencrypted_database",
        "DF-2 database storage not encrypted",
        frozenset({"aws_db_instance"}),
        frozenset({"CKV_AWS_16"}),
        frozenset({"CKV_AWS_16"}),
        "storage_encrypted",
    ),
    Family(
        "unencrypted_volume",
        "DF-2 EBS volume not encrypted",
        frozenset({"aws_ebs_volume"}),
        frozenset({"CKV_AWS_3"}),
        frozenset({"CKV_AWS_3"}),
        "encrypted",
    ),
    Family(
        "wildcard_policy",
        "DF-3 IAM policy allows Action * on Resource *",
        frozenset({"aws_iam_role_policy", "aws_iam_policy"}),
        frozenset({"CKV_AWS_1"}),
        frozenset({"CKV_AWS_1", "CKV_AWS_49", "CKV_AWS_63"}),
        "policy",
    ),
    Family(
        "cloudtrail_validation",
        "DF-4 CloudTrail log-file validation off",
        frozenset({"aws_cloudtrail"}),
        frozenset({"CKV_AWS_36"}),
        frozenset({"CKV_AWS_36"}),
        "enable_log_file_validation",
    ),
)


@dataclass(frozen=True, slots=True)
class CheckovResult:
    check_id: str
    resource: str
    passed: bool
    directory: str  # posix path of the file's directory, relative to the scanned root


def parse_results(data: Any) -> list[CheckovResult]:
    """Checkov's JSON into results that keep which directory each came from."""
    runs = data if isinstance(data, list) else [data]
    out: list[CheckovResult] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        results = run.get("results", {})
        for kind, passed in (("passed_checks", True), ("failed_checks", False)):
            for check in results.get(kind, []):
                where = str(
                    PurePosixPath(str(check.get("file_path", "")).replace("\\", "/")).parent
                )
                out.append(
                    CheckovResult(
                        str(check["check_id"]),
                        str(check["resource"]),
                        passed,
                        where.lstrip("/") or ".",
                    )
                )
    return out


def run_checkov_directory(directory: Path) -> list[CheckovResult]:
    """Run Checkov over a directory tree (a subprocess; nothing is imported or executed)."""
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "checkov.main",
            "-d",
            str(directory),
            "--framework",
            "terraform",
            "-o",
            "json",
            "--compact",
            "--soft-fail",
            "--quiet",
            "--skip-download",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # Third-party files hold non-ASCII text; Windows' default code page cannot read it.
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    out = done.stdout.strip()
    if not out:
        raise RuntimeError(
            f"checkov produced no output (rc={done.returncode}): {done.stderr[-300:]}"
        )
    return parse_results(json.loads(out))


def _blind(res: Resource, family: Family) -> bool:
    value = res.attributes.get(family.attribute)
    if family.attribute == "ingress":
        rules = value if isinstance(value, list) else []
        return any(
            isinstance(r, dict) and "${" in json.dumps(r.get("cidr_blocks", "")) for r in rules
        )
    return isinstance(value, str) and "${" in value


def evaluate(
    parsed: Sequence[ParsedDirectory], results: Sequence[CheckovResult], root: Path
) -> dict[str, Any]:
    """Per-family agreement between the rule floor and Checkov, plus how much falls outside."""
    failed_by_location: dict[tuple[str, str], set[str]] = {}
    for r in results:
        if not r.passed:
            failed_by_location.setdefault((r.directory, r.resource), set()).add(r.check_id)

    families: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    for family in FAMILIES:
        both = only_checkov = only_ours = neither = blind = 0
        missed: list[str] = []
        for directory in parsed:
            where = directory.directory.relative_to(root).as_posix() or "."
            for res in directory.resources:
                if res.type not in family.types:
                    continue
                ours = any(f.rule_id in family.ours for f in resource_findings(res))
                theirs = bool(failed_by_location.get((where, res.address), set()) & family.checkov)
                blinded = _blind(res, family) and not ours
                if ours and theirs:
                    both += 1
                elif theirs:
                    only_checkov += 1
                    blind += int(blinded)
                    missed.append(f"{where}/{res.address}")
                elif ours:
                    only_ours += 1
                else:
                    neither += 1
        seen = both + only_checkov + only_ours + neither
        families.append(
            {
                "family": family.key,
                "label": family.label,
                "resources_of_these_types": seen,
                "both_flag": both,
                "only_checkov_flags": only_checkov,
                "only_rule_floor_flags": only_ours,
                "neither_flags": neither,
                "missed_because_unresolved_expression": blind,
                "recall_against_checkov": round(both / (both + only_checkov), 3)
                if both + only_checkov
                else None,
                "missed_resources": sorted(missed)[:25],
            }
        )

    for directory in parsed:
        type_counts.update(r.type for r in directory.resources)
    failed = Counter(r.check_id for r in results if not r.passed)
    mapped = frozenset().union(*(f.checkov for f in FAMILIES))
    in_families = sum(n for cid, n in failed.items() if cid in mapped)
    return {
        "directories": len(parsed),
        "files_parsed": sum(d.files for d in parsed),
        "files_skipped": [f"{d.directory.name}/{s}" for d in parsed for s in d.skipped],
        "aws_resources": sum(type_counts.values()),
        "covered_types": {
            t: type_counts[t]
            for t in sorted({t for f in FAMILIES for t in f.types})
            if type_counts[t]
        },
        "families": families,
        "coverage": {
            "checkov_failed_checks": sum(failed.values()),
            "in_rule_floor_families": in_families,
            "share": round(in_families / sum(failed.values()), 3) if failed else None,
            "most_common_outside": [
                {"check_id": cid, "count": n}
                for cid, n in failed.most_common()
                if cid not in mapped
            ][:15],
        },
    }
