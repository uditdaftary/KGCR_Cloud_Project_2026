"""Structural features reflect the topology and never read the intent."""

from __future__ import annotations

from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import (
    Archetype,
    AZSpread,
    IAMShape,
    Intent,
    LoggingPosture,
    NetworkLayout,
    Scale,
    TaggingDiscipline,
)
from kgcr.corpus.sampler import IntentSampler
from kgcr.reconstruction.features import FEATURE_NAMES, extract_features, feature_vector


def _estate(archetype: Archetype, **overrides):
    base = {
        "archetype": archetype,
        "region": "eu-west-2",
        "az_spread": AZSpread.TWO_AZ,
        "network_layout": NetworkLayout.PUBLIC_PRIVATE,
        "logging": LoggingPosture.FULL,
        "iam_shape": IAMShape.LEAST_PRIVILEGE,
        "tagging": TaggingDiscipline.STRICT,
        "scale": Scale.MEDIUM,
    }
    base.update(overrides)
    return render_estate(Intent(**base), 7)


def test_feature_vector_matches_feature_names() -> None:
    vec = feature_vector(_estate(Archetype.PAYMENTS_API))
    assert len(vec) == len(FEATURE_NAMES)


def test_archetype_signatures_show_up_in_features() -> None:
    pay = extract_features(_estate(Archetype.PAYMENTS_API))
    rep = extract_features(_estate(Archetype.INTERNAL_REPORTING))
    assert pay["has_cardholder_db"] == 1.0
    assert pay["has_reporting_instance"] == 0.0
    assert rep["has_cardholder_db"] == 0.0
    assert rep["has_reporting_instance"] == 1.0


def test_tagging_discipline_shows_in_tag_richness() -> None:
    strict = extract_features(_estate(Archetype.PAYMENTS_API, tagging=TaggingDiscipline.STRICT))
    poor = extract_features(_estate(Archetype.PAYMENTS_API, tagging=TaggingDiscipline.POOR))
    assert strict["max_tag_keys"] > poor["max_tag_keys"]


def test_logging_posture_shows_in_cloudtrail_presence() -> None:
    full = extract_features(_estate(Archetype.PAYMENTS_API, logging=LoggingPosture.FULL))
    minimal = extract_features(_estate(Archetype.PAYMENTS_API, logging=LoggingPosture.MINIMAL))
    assert full["has_cloudtrail"] == 1.0
    assert minimal["has_cloudtrail"] == 0.0


def test_az_spread_shows_in_subnet_grouping() -> None:
    single = extract_features(_estate(Archetype.PAYMENTS_API, az_spread=AZSpread.SINGLE_AZ))
    three = extract_features(_estate(Archetype.PAYMENTS_API, az_spread=AZSpread.THREE_AZ))
    assert three["az_count_estimate"] > single["az_count_estimate"]


def test_features_are_purely_structural() -> None:
    # Two estates identical in structure but sampled independently must produce
    # identical features regardless of any intent bookkeeping.
    a = render_estate(IntentSampler(4).sample(Archetype.PAYMENTS_API), 9)
    b = render_estate(IntentSampler(4).sample(Archetype.PAYMENTS_API), 9)
    assert extract_features(a) == extract_features(b)
