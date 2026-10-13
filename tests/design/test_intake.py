"""Intake states every axis or refuses by name; it never defaults."""

from __future__ import annotations

import pytest

from kgcr.corpus.sampler import REGIONS
from kgcr.design.intake import AXES, IntakeError, axis_choices, build_intent

STATED = {
    "archetype": "payments_api",
    "region": "eu-west-1",
    "az_spread": "two_az",
    "network_layout": "public_private",
    "logging": "full",
    "iam_shape": "least_privilege",
    "tagging": "strict",
    "scale": "small",
}


def test_a_complete_statement_builds_the_intent() -> None:
    intent = build_intent(STATED)
    assert intent.archetype.value == "payments_api" and intent.region == "eu-west-1"
    assert intent.to_dict()["scale"] == "small"


def test_missing_axes_are_listed_not_defaulted() -> None:
    with pytest.raises(IntakeError) as exc:
        build_intent({"archetype": "payments_api", "region": "eu-west-1"})
    assert set(exc.value.missing) == set(AXES) - {"archetype", "region"}
    assert exc.value.invalid == {}


@pytest.mark.parametrize("blank", [None, ""])
def test_a_blank_value_counts_as_missing(blank: str | None) -> None:
    with pytest.raises(IntakeError) as exc:
        build_intent({**STATED, "scale": blank})
    assert exc.value.missing == ("scale",)


def test_an_invalid_value_is_named() -> None:
    with pytest.raises(IntakeError) as exc:
        build_intent({**STATED, "scale": "huge"})
    assert exc.value.invalid == {"scale": "huge"} and exc.value.missing == ()


def test_a_region_outside_the_known_set_is_refused() -> None:
    with pytest.raises(IntakeError) as exc:
        build_intent({**STATED, "region": "mars-1"})
    assert "region" in exc.value.invalid


def test_a_field_that_is_not_an_axis_is_refused() -> None:
    with pytest.raises(IntakeError) as exc:
        build_intent({**STATED, "budget": "10"})
    assert exc.value.invalid == {"budget": "not an intent axis"}


def test_choices_cover_every_axis_and_the_known_regions() -> None:
    choices = axis_choices()
    assert tuple(choices) == AXES and choices["region"] == REGIONS
