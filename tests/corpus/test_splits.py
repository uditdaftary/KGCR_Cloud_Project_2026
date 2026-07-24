"""Estate-level splitting must not leak — the FD-05 §9 guarantee."""

from __future__ import annotations

import pytest

from kgcr.corpus.pipeline import generate_corpus
from kgcr.corpus.splits import check_split_integrity, split_estates


def test_no_estate_appears_in_two_splits() -> None:
    estates = generate_corpus(120, seed=1)
    split = split_estates(estates)
    check_split_integrity(estates, split)  # raises on leakage


def test_no_seed_family_straddles_splits() -> None:
    # Families of 4 near-identical estates: the scenario resource-level splitting
    # would leak. Integrity must still hold.
    estates = generate_corpus(120, seed=2, family_size=4)
    split = split_estates(estates)
    check_split_integrity(estates, split)


def test_split_covers_every_estate_exactly_once() -> None:
    estates = generate_corpus(200, seed=3)
    split = split_estates(estates)
    assigned = split.train.estate_ids + split.validation.estate_ids + split.test.estate_ids
    assert sorted(assigned) == sorted(e.estate_id for e in estates)
    assert len(assigned) == len(set(assigned))


def test_split_is_deterministic() -> None:
    estates = generate_corpus(100, seed=4)
    assert split_estates(estates).as_dict() == split_estates(estates).as_dict()


def test_split_independent_of_input_order() -> None:
    estates = generate_corpus(100, seed=5)
    forward = split_estates(estates)
    backward = split_estates(list(reversed(estates)))
    assert forward.as_dict() == backward.as_dict()


def test_split_is_roughly_proportional() -> None:
    estates = generate_corpus(600, seed=6)
    split = split_estates(estates)
    n = len(estates)
    assert 0.6 < len(split.train.estate_ids) / n < 0.8
    assert 0.08 < len(split.validation.estate_ids) / n < 0.22
    assert 0.08 < len(split.test.estate_ids) / n < 0.22


def test_detects_injected_family_leak() -> None:
    # Force two estates of one family into different splits and confirm the
    # integrity check catches it.
    estates = generate_corpus(10, seed=7, family_size=2)
    families = {e.seed_family for e in estates}
    assert len(families) < len(estates)  # families really do group estates

    from kgcr.corpus.splits import CorpusSplit, Split

    a, b = estates[0], estates[1]
    assert a.seed_family == b.seed_family  # same family by construction
    bad = CorpusSplit(
        train=Split("train", (a.estate_id,)),
        validation=Split("validation", ()),
        test=Split("test", tuple(e.estate_id for e in estates if e is not a)),
    )
    with pytest.raises(ValueError, match="straddles"):
        check_split_integrity(estates, bad)


def test_invalid_fractions_rejected() -> None:
    estates = generate_corpus(5, seed=8)
    with pytest.raises(ValueError):
        split_estates(estates, train=0.9, validation=0.2)
