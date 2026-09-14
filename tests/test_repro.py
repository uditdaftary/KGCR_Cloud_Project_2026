"""Seeding must be deterministic and honestly reported."""

from __future__ import annotations

import random

import pytest

from kgcr.repro import DEFAULT_SEED, hash_seed_is_fixed, seed_everything


def test_same_seed_gives_same_python_random_sequence() -> None:
    seed_everything(42)
    first = [random.random() for _ in range(5)]
    seed_everything(42)
    second = [random.random() for _ in range(5)]
    assert first == second


def test_different_seed_gives_different_sequence() -> None:
    seed_everything(1)
    first = [random.random() for _ in range(5)]
    seed_everything(2)
    second = [random.random() for _ in range(5)]
    assert first != second


def test_report_flags_python_random_true() -> None:
    report = seed_everything(DEFAULT_SEED)
    assert report.python_random is True
    assert report.seed == DEFAULT_SEED


def test_report_pythonhashseed_matches_probe() -> None:
    report = seed_everything()
    assert report.pythonhashseed == hash_seed_is_fixed()


def test_negative_seed_rejected() -> None:
    with pytest.raises(ValueError):
        seed_everything(-1)
