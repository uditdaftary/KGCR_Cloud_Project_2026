"""The skeleton is audited by the recommender; the CRITICAL mask is a hard stop."""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from kgcr.corpus.pipeline import generate_corpus  # noqa: E402
from kgcr.defects.pipeline import inject_corpus  # noqa: E402
from kgcr.design.intake import build_intent  # noqa: E402
from kgcr.design.synthesize import MaskViolation, synthesize  # noqa: E402
from kgcr.recommender.recommender import OptionRecommender, RankedOption  # noqa: E402

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
SEED = 1729


@pytest.fixture(scope="module")
def recommender() -> OptionRecommender:
    clean = generate_corpus(60, SEED)
    rec = OptionRecommender(random_state=0)
    rec.fit(clean, [d.estate for d in inject_corpus(clean)])
    return rec


def test_the_candidate_is_a_clean_skeleton_with_an_audit(recommender: OptionRecommender) -> None:
    candidate = synthesize(INTENT, SEED, recommender)
    assert candidate.estate.intent == INTENT and candidate.estate.resources
    assert candidate.recommended
    # Applied options come from the masked recommendation, never from outside it.
    wanted = {r.option for r in candidate.recommended if r.score >= 0.5}
    assert set(candidate.applied) <= wanted
    assert not any(recommender.is_masked(o) for o in candidate.applied)


def test_a_skeleton_holding_a_masked_option_fails_loudly(
    recommender: OptionRecommender, monkeypatch: pytest.MonkeyPatch
) -> None:
    flagged = ("aws_db_instance", "storage_encrypted", "True")
    assert flagged in recommender.candidates
    monkeypatch.setattr(recommender, "is_masked", lambda option: option == flagged)
    with pytest.raises(MaskViolation, match="storage_encrypted"):
        synthesize(INTENT, SEED, recommender)


def test_a_missing_option_on_a_single_resource_type_is_patched(
    recommender: OptionRecommender, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra = ("aws_db_instance", "engine", "mysql")
    real = recommender.recommend
    monkeypatch.setitem(recommender.raw_values, extra, "mysql")
    monkeypatch.setattr(
        recommender, "recommend", lambda intent: [*real(intent), RankedOption(extra, 0.9)]
    )
    candidate = synthesize(INTENT, SEED, recommender)
    assert extra in candidate.applied
    database = next(r for r in candidate.estate.resources if r.type == "aws_db_instance")
    assert database.attributes["engine"] == "mysql"


def test_a_missing_option_on_an_absent_type_is_reported_not_added(
    recommender: OptionRecommender, monkeypatch: pytest.MonkeyPatch
) -> None:
    absent = ("aws_nat_gateway", "present", "true")
    real = recommender.recommend
    monkeypatch.setattr(
        recommender, "recommend", lambda intent: [*real(intent), RankedOption(absent, 0.9)]
    )
    before = synthesize(INTENT, SEED, recommender)
    assert absent in before.reported_missing and absent not in before.applied
    assert all(r.type != "aws_nat_gateway" for r in before.estate.resources)


def test_synthesis_is_deterministic(recommender: OptionRecommender) -> None:
    a = synthesize(INTENT, SEED, recommender)
    b = synthesize(INTENT, SEED, recommender)
    assert a.estate == b.estate and a.applied == b.applied
