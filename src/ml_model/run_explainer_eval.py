"""Run the automated FD-06 evaluation and write ``results/explainer_report.json``.

Reviews each of the nine seeded variants (recorded model responses replay where they exist)
and designs three estates, then measures cross-audience invariance, counterfactual validity,
sparsity and relational fidelity over the stored bundles. See ``kgcr.explainer.evaluate`` for
exactly what each figure is and is not.

    python src/ml_model/run_explainer_eval.py --count 180
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from kgcr.advisor.llm import default_llm
from kgcr.defects.inject import INJECTORS
from kgcr.design.intake import build_intent
from kgcr.explainer.evaluate import EvalCase, evaluate_cases
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier
from kgcr.orchestration.design import run_design
from kgcr.orchestration.review import run_review
from kgcr.repro import DEFAULT_SEED

DEFAULT_REPORT = Path("results/explainer_report.json")
DESIGNS = (
    (
        "payments_api",
        "eu-west-1",
        "two_az",
        "public_private",
        "full",
        "least_privilege",
        "strict",
        "small",
    ),
    (
        "customer_data_platform",
        "us-east-1",
        "three_az",
        "private_with_nat",
        "minimal",
        "role_per_service",
        "partial",
        "large",
    ),
    (
        "internal_reporting",
        "eu-west-2",
        "single_az",
        "public_only",
        "full",
        "least_privilege",
        "poor",
        "medium",
    ),
)
AXES = (
    "archetype",
    "region",
    "az_spread",
    "network_layout",
    "logging",
    "iam_shape",
    "tagging",
    "scale",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    cases: list[EvalCase] = []
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(Path(tmp))
        for injector in INJECTORS:
            run = run_review(
                variant=injector.variant,
                store=store,
                notifier=LogNotifier(),
                llm=default_llm(),
                count=args.count,
                seed=args.seed,
            )
            cases.append(
                EvalCase(
                    injector.variant, run.target.estate, run.bundle, run.reviewed_findings, run.loop
                )
            )
            print(f"reviewed {injector.variant}", flush=True)
        for values in DESIGNS:
            design = run_design(
                intent=build_intent(dict(zip(AXES, values, strict=True))),
                store=store,
                notifier=LogNotifier(),
                llm=default_llm(),
                count=args.count,
                seed=args.seed,
            )
            cases.append(
                EvalCase(
                    f"design:{values[0]}",
                    design.candidate.estate,
                    design.bundle,
                    design.reviewed_findings,
                    design.loop,
                )
            )
            print(f"designed {values[0]}", flush=True)

    report = evaluate_cases(cases)
    report["cases"] = [c.name for c in cases]
    report["read_this_as"] = (
        "Automated FD-06 section 9.1 and 9.2 results over the stored bundles. The samples are "
        "small and every figure carries its n. The human study (9.3) is not run: it needs "
        "ethics approval and participants."
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for key in (
        "cross_audience_invariance",
        "counterfactual_validity",
        "sparsity",
        "fidelity_plus",
        "fidelity_minus",
    ):
        print(f"{key}: {report[key]}")
    print(f"report: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
