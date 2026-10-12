"""The recommender ranks options for an intent, and the mask is a hard output filter.

One experiment is fitted per module; the assertions read different facets of it.
The mask gate test forces a CRITICAL-violating option to the top of the ranking
and checks the filter still removes it (roadmap P7: "verify the mask removes
every CRITICAL-violating option after ranking").
"""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from kgcr.corpus.pipeline import generate_corpus  # noqa: E402
from kgcr.recommender.evaluate import run_recommender_experiment  # noqa: E402
from kgcr.recommender.recommender import (  # noqa: E402
    RankedOption,
    estate_options,
)


@pytest.fixture(scope="module")
def experiment():
    return run_recommender_experiment(generate_corpus(180, seed=1729))


def test_options_exclude_identity_attributes() -> None:
    # Names, tags, cidrs and references identify a resource rather than configure
    # it; leaving them in lets a model memorise addresses like df7_public_hop.
    for estate in generate_corpus(5, seed=7):
        for _type, attribute, _value in estate_options(estate):
            assert attribute not in {"name", "identifier", "tags", "cidr_block", "bucket"}
            assert not attribute.startswith("__ref__")


def test_candidate_pool_contains_critical_options(experiment) -> None:
    # Retrieval draws on the defect corpus too, so the mask has real work to do.
    masked = [o for o in experiment.recommender.candidates if experiment.recommender.is_masked(o)]
    assert ("aws_db_instance", "storage_encrypted", "False") in masked


def test_mask_removes_a_critical_option_forced_to_rank_one(experiment) -> None:
    rec = experiment.recommender
    bad = ("aws_db_instance", "storage_encrypted", "False")
    ranked = [RankedOption(bad, 1.0), *(RankedOption(o, 0.5) for o in rec.candidates if o != bad)]
    kept = rec.apply_mask(ranked)
    assert bad not in {r.option for r in kept}
    assert all(not rec.is_masked(r.option) for r in kept)


def test_recommend_output_is_masked(experiment) -> None:
    rec = experiment.recommender
    intent = generate_corpus(1, seed=3)[0].intent.to_dict()
    assert all(not rec.is_masked(r.option) for r in rec.recommend(intent))


def test_model_beats_baselines_on_held_out_split(experiment) -> None:
    report = experiment.report
    assert report["n_test"] > 0
    model = report["rankers"]["model_true_intent"]
    for baseline in ("popularity", "archetype_frequency"):
        assert model["exact_set"] >= report["rankers"][baseline]["exact_set"]
        assert model["r_precision"] >= report["rankers"][baseline]["r_precision"]
