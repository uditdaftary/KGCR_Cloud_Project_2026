"""The FD-06 evaluation metrics measure something: each one can fail."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from kgcr.advisor.llm import default_llm  # noqa: E402
from kgcr.explainer import evaluate as ev  # noqa: E402
from kgcr.explainer.evaluate import EvalCase, evaluate_cases  # noqa: E402
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier  # noqa: E402
from kgcr.orchestration.review import run_review  # noqa: E402


def _case(tmp: Path, variant: str, llm, count: int) -> EvalCase:  # type: ignore[no-untyped-def]
    run = run_review(
        variant=variant, store=LocalArtifactStore(tmp), notifier=LogNotifier(), llm=llm, count=count
    )
    return EvalCase(variant, run.target.estate, run.bundle, run.reviewed_findings, run.loop)


@pytest.fixture(scope="module")
def encryption_case(tmp_path_factory: pytest.TempPathFactory) -> EvalCase:
    return _case(tmp_path_factory.mktemp("eval-df2"), "unencrypted_database", None, 60)


@pytest.fixture(scope="module")
def relational_case(tmp_path_factory: pytest.TempPathFactory) -> EvalCase:
    # Recorded model responses replay for this variant at the default corpus (seed 1729, 180).
    return _case(tmp_path_factory.mktemp("eval-df7"), "transitive_trust_chain", default_llm(), 180)


def test_a_single_resource_repair_agrees_with_what_the_loop_then_observed(
    encryption_case: EvalCase,
) -> None:
    report = evaluate_cases([encryption_case])
    assert report["cross_audience_invariance"] == {"n": 1, "rate": 1.0}
    validity = report["counterfactual_validity"]
    assert (validity["n"], validity["rate"]) == (1, 1.0)
    assert 0 < report["sparsity"]["max"] <= 1
    assert report["findings"]["single_resource"] == 1 and report["findings"]["relational"] == 0
    # No relational finding here, so there is nothing to measure and no number is made up.
    assert report["fidelity_plus"]["rate"] is None and report["fidelity_plus"]["n"] == 0


def test_counterfactual_validity_can_fail(encryption_case: EvalCase) -> None:
    finding = encryption_case.bundle.findings[0]
    assert finding.counterfactual is not None and finding.counterfactual.resolved
    wrong = replace(finding, counterfactual=replace(finding.counterfactual, resolved=False))
    bundle = replace(encryption_case.bundle, findings=(wrong,))
    report = evaluate_cases([replace(encryption_case, bundle=bundle)])
    assert report["counterfactual_validity"]["rate"] == 0.0


def test_invariance_can_fail(encryption_case: EvalCase, monkeypatch: pytest.MonkeyPatch) -> None:
    real = ev.render

    def drifting(bundle, audience):  # type: ignore[no-untyped-def]
        text = real(bundle, audience)
        # A resource the other renderings never mention: a claim only the learner would make.
        return text + "\nAlso see aws_made_up.thing.\n" if audience == "learner" else text

    monkeypatch.setattr(ev, "render", drifting)
    assert evaluate_cases([encryption_case])["cross_audience_invariance"]["rate"] == 0.0


def test_relational_findings_are_measured_for_fidelity(relational_case: EvalCase) -> None:
    report = evaluate_cases([relational_case])
    if report["findings"]["relational"] == 0:
        pytest.skip("no recorded relational finding replays at this corpus")
    # Removing the evidence path removes the path; keeping only it keeps the path.
    assert report["fidelity_plus"]["n"] >= 1 and report["fidelity_plus"]["rate"] == 1.0
    assert report["fidelity_minus"]["rate"] == 1.0
    assert report["counterfactual_validity"]["not_checked"].startswith("relational")


def test_no_cases_reports_no_numbers() -> None:
    report = evaluate_cases([])
    assert report["bundles"] == 0 and report["cross_audience_invariance"]["rate"] is None
    assert report["sparsity"]["mean"] is None
