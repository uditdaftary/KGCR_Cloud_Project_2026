"""Explainer: evaluated counterfactuals and the INV-2 cross-audience invariance test."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from kgcr.advisor.advisor import Advisor, AdvisorFinding  # noqa: E402
from kgcr.advisor.controls import load_controls  # noqa: E402
from kgcr.advisor.loop import TemplatePatcher, advisor_loop  # noqa: E402
from kgcr.corpus.pipeline import generate_corpus  # noqa: E402
from kgcr.defects.inject import DefectedEstate  # noqa: E402
from kgcr.defects.pipeline import inject_corpus  # noqa: E402
from kgcr.explainer.explainer import (  # noqa: E402
    AUDIENCES,
    build_bundle,
    extract_claims,
    render,
)
from kgcr.recommender.recommender import OptionRecommender  # noqa: E402


@pytest.fixture(scope="module")
def setup():
    corpus = generate_corpus(30, seed=1729)
    defected = inject_corpus(corpus)
    rec = OptionRecommender()
    rec.fit(corpus, [d.estate for d in defected])
    return defected, TemplatePatcher(rec.templates), load_controls()


def _relational(d: DefectedEstate) -> AdvisorFinding:
    # Stands in for an admitted LLM finding: the injected ground-truth path.
    return AdvisorFinding(
        d.defect.control,
        load_controls()[d.defect.control].severity,
        (d.defect.injection_site[0],),
        "sensitive store reachable through a chain of individually compliant resources",
        "llm",
        d.defect.evidence_path,
    )


def _bundle(d: DefectedEstate, patcher: TemplatePatcher, controls):
    result = advisor_loop(d.estate, d.estate.intent.to_dict(), Advisor(), patcher)
    findings = list(result.passes[0].findings)
    if d.defect.is_relational:
        findings.append(_relational(d))
    return build_bundle(
        d.estate,
        findings,
        controls,
        patcher,
        loop_status=result.status,
        loop_reason=result.reason,
    )


def test_inv2_claims_identical_across_audiences_for_every_variant(setup) -> None:
    defected, patcher, controls = setup
    variants: dict[str, DefectedEstate] = {}
    for d in defected:
        variants.setdefault(d.defect.variant, d)
    for variant, d in variants.items():
        claims = {a: extract_claims(render(_bundle(d, patcher, controls), a)) for a in AUDIENCES}
        assert claims["architect"], variant
        assert claims["architect"] == claims["auditor"] == claims["learner"], variant


def test_extractor_notices_a_dropped_claim(setup) -> None:
    defected, patcher, controls = setup
    d = next(x for x in defected if x.defect.variant == "unencrypted_database")
    text = render(_bundle(d, patcher, controls), "auditor")
    assert extract_claims(text) != extract_claims(text.replace("aws_db_instance.cardholder", "it"))


def test_counterfactuals_are_evaluated_not_asserted(setup) -> None:
    defected, patcher, controls = setup
    d2 = next(x for x in defected if x.defect.variant == "unencrypted_database")
    rule = _bundle(d2, patcher, controls).findings[0].counterfactual
    assert rule is not None and rule.resolved

    d7 = next(x for x in defected if x.defect.variant == "privilege_escalation_passrole")
    bundle = _bundle(d7, patcher, controls)
    relational = next(f for f in bundle.findings if f.evidence_path)
    assert relational.counterfactual is not None
    # Cutting the last hop either breaks the path or names the path that survives.
    cf = relational.counterfactual
    assert cf.resolved or "another path remains" in cf.detail


def test_unknown_audience_is_rejected(setup) -> None:
    defected, patcher, controls = setup
    with pytest.raises(ValueError):
        render(_bundle(defected[0], patcher, controls), "executive")
