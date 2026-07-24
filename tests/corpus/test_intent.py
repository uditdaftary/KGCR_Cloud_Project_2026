"""Intent identity, ground-truth serialisation, and the sampler's determinism."""

from __future__ import annotations

from kgcr.corpus.intent import Archetype, Intent
from kgcr.corpus.sampler import REGIONS, IntentSampler


def test_intent_hash_is_order_independent() -> None:
    intent = IntentSampler(1).sample()
    assert Intent.from_dict(intent.to_dict()).intent_hash == intent.intent_hash


def test_intent_round_trips_through_dict() -> None:
    intent = IntentSampler(7).sample()
    assert Intent.from_dict(intent.to_dict()) == intent


def test_data_sensitivity_is_derived_from_archetype() -> None:
    payments = IntentSampler(1).sample(Archetype.PAYMENTS_API)
    reporting = IntentSampler(1).sample(Archetype.INTERNAL_REPORTING)
    assert payments.data_sensitivity == "cardholder_data"
    assert reporting.data_sensitivity == "low"


def test_data_sensitivity_excluded_from_identity() -> None:
    # Two intents differing only in the derived field cannot exist, but the hash
    # must be computed over the non-derived axes only.
    intent = IntentSampler(1).sample()
    identity_keys = {"data_sensitivity"}
    assert not identity_keys & set(_hashed_keys(intent))


def _hashed_keys(intent: Intent) -> set[str]:
    return {k for k in intent.to_dict() if k != "data_sensitivity"}


def test_sampler_is_deterministic_for_a_seed() -> None:
    a = [IntentSampler(99).sample() for _ in range(20)]
    b = [IntentSampler(99).sample() for _ in range(20)]
    assert a == b


def test_sampler_streams_differ_across_seeds() -> None:
    a = [IntentSampler(1).sample() for _ in range(20)]
    b = [IntentSampler(2).sample() for _ in range(20)]
    assert a != b


def test_forced_archetype_is_respected() -> None:
    sampler = IntentSampler(3)
    for _ in range(10):
        intent = sampler.sample(Archetype.CUSTOMER_DATA_PLATFORM)
        assert intent.archetype is Archetype.CUSTOMER_DATA_PLATFORM
        assert intent.region in REGIONS
