"""A designed spec is justified by its rejected alternatives, and INV-2 still holds."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("sklearn")

from kgcr.advisor.advisor import Advisor  # noqa: E402
from kgcr.advisor.loop import TemplatePatcher  # noqa: E402
from kgcr.corpus.pipeline import generate_corpus  # noqa: E402
from kgcr.defects.pipeline import inject_corpus  # noqa: E402
from kgcr.design.intake import build_intent  # noqa: E402
from kgcr.design.synthesize import synthesize  # noqa: E402
from kgcr.explainer.design import build_justifications  # noqa: E402
from kgcr.explainer.explainer import (  # noqa: E402
    AUDIENCES,
    ExplanationBundle,
    build_bundle,
    bundle_json,
    extract_claims,
    render,
)
from kgcr.recommender.recommender import OptionRecommender  # noqa: E402

INTENT = build_intent(
    {
        "archetype": "payments_api",
        "region": "eu-west-1",
        "az_spread": "two_az",
        "network_layout": "public_private",
        "logging": "full",
        "iam_shape": "least_privilege",
        "tagging": "strict",
        "scale": "small",
    }
)


@pytest.fixture(scope="module")
def designed():  # type: ignore[no-untyped-def]
    clean = generate_corpus(60, 1729)
    recommender = OptionRecommender(random_state=0)
    recommender.fit(clean, [d.estate for d in inject_corpus(clean)])
    candidate = synthesize(INTENT, 1729, recommender)
    advisor = Advisor(None)
    justifications, unconstrained = build_justifications(
        candidate.estate, recommender, advisor.controls
    )
    bundle = build_bundle(
        candidate.estate,
        (),
        advisor.controls,
        TemplatePatcher(recommender.templates),
        loop_status="CONVERGED",
        loop_reason="CLEAN",
    )
    from dataclasses import replace

    return replace(bundle, justifications=justifications, unconstrained_choices=unconstrained)


def test_the_unencrypted_database_alternative_is_the_critical_justification(designed) -> None:  # type: ignore[no-untyped-def]
    storage = next(
        j
        for j in designed.justifications
        if j.attribute == "storage_encrypted" and j.element.startswith("aws_db_instance.")
    )
    assert storage.chosen == "True"
    worst = storage.alternatives[0]
    assert worst.value == "False" and worst.severity.value == "CRITICAL"
    assert worst.control_ref == "PCI-DSS-4.0-3.5.1"


def test_unconstrained_choices_are_counted_not_narrated(designed) -> None:  # type: ignore[no-untyped-def]
    assert designed.unconstrained_choices > 0
    text = render(designed, "architect")
    assert f"{designed.unconstrained_choices} further choices are not constrained" in text
    assert all(j.alternatives for j in designed.justifications)


def test_every_audience_makes_the_same_claims(designed) -> None:  # type: ignore[no-untyped-def]
    # INV-2: the audience changes the wording, never what is claimed.
    claims = [extract_claims(render(designed, a)) for a in AUDIENCES]
    assert claims[0] and all(c == claims[0] for c in claims)
    assert "CRITICAL" in claims[0] and "PCI-DSS-4.0-3.5.1" in claims[0]


def test_a_design_bundle_round_trips_byte_for_byte(designed) -> None:  # type: ignore[no-untyped-def]
    text = bundle_json(designed)
    assert "design" in json.loads(text)
    assert bundle_json(ExplanationBundle.from_dict(json.loads(text))) == text


def test_a_review_bundle_has_no_design_key_so_stored_bundles_are_unchanged() -> None:
    plain = ExplanationBundle("e", "CONVERGED", "CLEAN", ())
    assert "design" not in plain.to_dict()
    assert ExplanationBundle.from_dict(plain.to_dict()) == plain
