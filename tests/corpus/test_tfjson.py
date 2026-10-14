"""Terraform JSON loads back into the resources it was rendered from."""

from __future__ import annotations

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.corpus.sampler import IntentSampler
from kgcr.corpus.tfjson import resources_from_terraform_json


def _comparable(resources):  # type: ignore[no-untyped-def]
    return sorted(
        ((r.type, r.name, r.attributes, tuple(sorted(r.references))) for r in resources),
        key=lambda row: (row[0], row[1]),
    )


def test_round_trip_over_generated_estates() -> None:
    for seed in range(40):
        estate = render_estate(IntentSampler(seed).sample(), seed)
        loaded = resources_from_terraform_json(estate.to_terraform_json())
        assert _comparable(loaded) == _comparable(estate.resources)


def test_interpolation_becomes_a_ref_marker_and_a_reference() -> None:
    doc = {
        "resource": {
            "aws_vpc": {"main": {"cidr_block": "10.0.0.0/16"}},
            "aws_subnet": {"a": {"vpc_id": "${aws_vpc.main.id}", "depends_on": ["aws_vpc.main"]}},
        }
    }
    by_type = {r.type: r for r in resources_from_terraform_json(doc)}
    subnet = by_type["aws_subnet"]
    assert subnet.attributes == {"__ref__vpc_id": "aws_vpc.main"}
    assert "aws_vpc.main" in subnet.references


def test_a_document_without_resources_is_empty() -> None:
    assert resources_from_terraform_json({"provider": {"aws": {"region": "eu-west-1"}}}) == ()


@pytest.mark.parametrize(
    "doc",
    [
        {"resource": {"aws_vpc": ["not", "a", "mapping"]}},
        {"resource": {"aws_vpc": {"main": "not a body"}}},
        {"resource": ["x"]},
    ],
)
def test_rejects_malformed_documents(doc: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        resources_from_terraform_json(doc)
