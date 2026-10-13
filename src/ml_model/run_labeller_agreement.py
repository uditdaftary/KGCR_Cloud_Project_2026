"""Compare the rule floor, Checkov and Trivy on seeded and clean estates.

For each single-resource defect family (DF-1 to DF-4) this takes estates the injector can
seed, runs all three engines on the clean parent and on the defected child, and writes
``results/labeller_agreement.json``: seeded recall, false positives on the clean parent, and
pairwise agreement with Cohen's kappa. Needs the ``labelling`` extra (Checkov) and Trivy.

Checkov reads the estate as ``terraform show -json`` plan output by default (needs Terraform),
because its ``.tf.json`` parser evaluates these single-resource checks unreliably; the
``--checkov-input tfjson`` run is kept as the evidence for that claim.

    python src/ml_model/run_labeller_agreement.py --per-family 6
    python src/ml_model/run_labeller_agreement.py --checkov-input tfjson \
        --report-out results/labeller_agreement_tfjson.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from kgcr.corpus.estate import Estate
from kgcr.corpus.pipeline import generate_corpus
from kgcr.defects.inject import applicable_injectors
from kgcr.labelling.agreement import FAMILIES, evaluate_labellers
from kgcr.labelling.checkov_engine import (
    CheckovFinding,
    checkov_available,
    run_checkov,
    run_checkov_on_plan,
)
from kgcr.labelling.trivy_engine import run_trivy, trivy_available, trivy_binary
from kgcr.plan.terraform_backend import SubprocessRunner, plan_document, terraform_available
from kgcr.repro import DEFAULT_SEED

DEFAULT_REPORT = Path("results/labeller_agreement.json")


def _version(cmd: list[str]) -> str:
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return (
        (done.stdout or done.stderr).strip().splitlines()[0]
        if (done.stdout or done.stderr)
        else "?"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-family", type=int, default=6, help="Seeded estates per family")
    parser.add_argument("--count", type=int, default=180, help="Corpus size to draw from")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--checkov-input", choices=("plan", "tfjson"), default="plan")
    parser.add_argument(
        "--plugin-cache", type=Path, default=Path("ui-store/tf/.plugin-cache"), help="Terraform"
    )
    args = parser.parse_args()
    if not checkov_available() or not trivy_available():
        print("both Checkov (the labelling extra) and trivy are needed", file=sys.stderr)
        return 2
    if args.checkov_input == "plan" and not terraform_available():
        print("--checkov-input plan needs terraform on PATH", file=sys.stderr)
        return 2

    corpus = generate_corpus(args.count, args.seed)
    pairs: dict[str, list[tuple[Estate, Estate, str]]] = {}
    for family in FAMILIES:
        rows: list[tuple[Estate, Estate, str]] = []
        for estate in corpus:
            match = [i for i in applicable_injectors(estate) if i.variant == family.key]
            if match:
                defected = match[0].run(estate)
                rows.append((estate, defected.estate, defected.defect.injection_site[0]))
            if len(rows) == args.per_family:
                break
        pairs[family.key] = rows
        print(f"{family.key}: {len(rows)} seeded estates", flush=True)

    with tempfile.TemporaryDirectory() as workdir:
        if args.checkov_input == "plan":
            runner = SubprocessRunner()

            def checkov(estate: Estate) -> list[CheckovFinding]:
                # One working directory: init runs once, every later call only re-plans.
                plan = plan_document(
                    estate.to_terraform_json(),
                    Path(workdir),
                    runner,
                    plugin_cache=args.plugin_cache,
                )
                return run_checkov_on_plan(plan.plan_json)

        else:
            checkov = run_checkov
        report = evaluate_labellers(pairs, checkov, run_trivy)
    report["checkov_input"] = args.checkov_input
    report["engines"] = {
        "checkov": _version([sys.executable, "-m", "checkov.main", "--version"]),
        "trivy": _version([trivy_binary() or "trivy", "--version"]),
    }
    report["read_this_as"] = (
        "Per family and per engine: how often the engine flags the seeded defect, how often it "
        "flags the same resource in the clean parent, and how the engines agree with each "
        "other. Where an engine defines the defect differently from the injector (for example "
        "a security group open on port 443), a disagreement is a finding about the definition, "
        "not an error in the engine. Checkov reads .tf.json inconsistently for single-resource "
        "checks on interpolated configurations (see the CHANGELOG)."
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for fam in report["families"]:
        print(
            f"{fam['label']:<46} n={fam['seeded_defects']} recall={fam['seeded_recall']} "
            f"false_pos={fam['false_positives_on_clean']}"
        )
    print(f"report: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
