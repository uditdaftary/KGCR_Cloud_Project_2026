"""Reconstruction recovers intent from topology, and its confidence is calibrated.

One experiment is fitted per module (shared fixture) and the assertions read
different facets of it: accuracy on the structurally-encoded axes, and the honest
low confidence on ``iam_shape`` — the axis the generator leaves no trace of.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from kgcr.corpus.pipeline import generate_corpus  # noqa: E402
from kgcr.corpus.splits import split_estates  # noqa: E402
from kgcr.reconstruction.pipeline import run_reconstruction_experiment  # noqa: E402
from kgcr.reconstruction.reconstructor import IntentReconstructor  # noqa: E402


@pytest.fixture(scope="module")
def experiment():
    return run_reconstruction_experiment(generate_corpus(180, seed=1729))


def test_reconstructs_every_field_with_a_probability(experiment) -> None:
    corpus = generate_corpus(5, seed=99)
    for estate in corpus:
        recovered = experiment.reconstructor.reconstruct(estate)
        for field, rf in recovered.fields.items():
            assert 0.0 <= rf.confidence <= 1.0, field


def test_structurally_encoded_axes_are_recovered_well(experiment) -> None:
    report = experiment.report
    # These axes leave a clear structural trace and should be recovered reliably.
    for field in ("archetype", "network_layout", "logging"):
        assert report.per_field[field].accuracy > 0.9, field


def test_iam_shape_is_the_uncalibrated_axis(experiment) -> None:
    # The generator renders iam_shape identically, so it leaves no structural
    # signal. The reconstructor is therefore least accurate here, and — the
    # calibration story — most miscalibrated: its confidence most exceeds its
    # accuracy, which is exactly what the reliability diagram exists to surface
    # (and what a naive confidence threshold would miss).
    per_field = experiment.report.per_field
    iam = per_field["iam_shape"]
    assert iam.accuracy == min(fe.accuracy for fe in per_field.values())
    assert iam.expected_calibration_error == max(
        fe.expected_calibration_error for fe in per_field.values()
    )
    assert iam.mean_confidence < per_field["archetype"].mean_confidence


def test_calibration_bins_account_for_every_prediction(experiment) -> None:
    for fe in experiment.report.per_field.values():
        assert sum(b.count for b in fe.bins) == fe.n
        assert 0.0 <= fe.expected_calibration_error <= 1.0


def test_beats_a_majority_class_baseline(experiment) -> None:
    # A 3-way archetype guess is 1/3 at chance; reconstruction must clear that.
    assert experiment.report.overall_accuracy > 0.5


def test_experiment_honours_the_estate_level_split() -> None:
    estates = generate_corpus(180, seed=1729)
    split = split_estates(estates)
    train_families = {e.seed_family for e in estates if e.estate_id in set(split.train.estate_ids)}
    test_families = {e.seed_family for e in estates if e.estate_id in set(split.test.estate_ids)}
    assert train_families.isdisjoint(test_families)


def test_reconstruct_before_fit_raises() -> None:
    corpus = generate_corpus(1, seed=1)
    with pytest.raises(RuntimeError, match="not fitted"):
        IntentReconstructor().reconstruct(corpus[0])
