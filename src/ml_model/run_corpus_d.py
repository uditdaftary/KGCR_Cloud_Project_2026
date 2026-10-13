"""Measure the rule floor against corpus D and write ``results/corpus_d_report.json``.

Parses the AWS Terraform in the acquired repositories, runs Checkov over the same files as an
independent comparison, and reports per-family agreement and how much of what Checkov fails
lies outside the rule floor's seven rules. TerraGoat and CloudGoat are vulnerable by design
and carry no per-resource labels, so this reports agreement and coverage, not accuracy.

    python src/ml_model/run_corpus_d.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from kgcr.adversarial.evaluate import evaluate, run_checkov_directory
from kgcr.adversarial.hcl import load_hcl_directory

DEFAULT_ROOT = Path("dataset/raw/corpus_d")
DEFAULT_MANIFEST = Path("dataset/processed/corpus_d_manifest.json")
DEFAULT_REPORT = Path("results/corpus_d_report.json")


def _scan(artifact_id: str, root: Path) -> tuple[Path, list[Path]]:
    """The directory Checkov scans, and the module directories inside it."""
    if artifact_id == "terragoat":
        scan = root / "terragoat" / "terraform" / "aws"
        return scan, [scan]
    scan = root / "cloudgoat" / "cloudgoat" / "scenarios" / "aws"
    # Only each scenario's deployed infrastructure; its attacker-side solution code is not it.
    return scan, sorted(p for p in scan.glob("*/terraform") if p.is_dir())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "corpus": "D: independently authored, deliberately vulnerable Terraform (FD-05 4D)",
        "read_this_as": (
            "Agreement between the rule floor and Checkov on configurations this project did not "
            "write, and how much of what Checkov fails lies outside the rule floor's seven rules. "
            "The repositories carry no per-resource labels, so this is not accuracy. The family "
            "map is this project's own. The rule floor reads literal values only."
        ),
        "artifacts": manifest["artifacts"],
        "repositories": {},
    }
    for artifact in manifest["artifacts"]:
        scan, directories = _scan(artifact["artifact_id"], args.root)
        parsed = [load_hcl_directory(d) for d in directories]
        results = run_checkov_directory(scan)
        evaluated = evaluate(parsed, results, scan)
        report["repositories"][artifact["artifact_id"]] = evaluated
        print(
            f"{artifact['artifact_id']}: {evaluated['aws_resources']} AWS resources in "
            f"{evaluated['directories']} directories; Checkov failed "
            f"{evaluated['coverage']['checkov_failed_checks']} checks, "
            f"{evaluated['coverage']['in_rule_floor_families']} in the rule floor's families"
        )
        for fam in evaluated["families"]:
            print(
                f"  {fam['label']:<52} n={fam['resources_of_these_types']:>3} "
                f"both={fam['both_flag']:>3} only_checkov={fam['only_checkov_flags']:>3} "
                f"only_ours={fam['only_rule_floor_flags']:>3} "
                f"recall={fam['recall_against_checkov']}"
            )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"report: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
