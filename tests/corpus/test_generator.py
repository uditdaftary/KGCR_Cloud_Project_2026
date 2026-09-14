"""The generator is deterministic, intent-preserving, and emits valid config."""

from __future__ import annotations

from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import Archetype
from kgcr.corpus.sampler import IntentSampler


def _intent(seed: int, archetype: Archetype | None = None):
    return IntentSampler(seed).sample(archetype)


def test_same_intent_and_seed_render_identically() -> None:
    intent = _intent(1)
    a = render_estate(intent, 42)
    b = render_estate(intent, 42)
    assert a.to_dict() == b.to_dict()
    assert a.estate_id == b.estate_id


def test_different_seed_changes_estate_id() -> None:
    intent = _intent(1)
    assert render_estate(intent, 1).estate_id != render_estate(intent, 2).estate_id


def test_estate_carries_originating_intent_as_ground_truth() -> None:
    intent = _intent(5)
    estate = render_estate(intent, 3)
    assert estate.intent == intent
    assert estate.intent.intent_hash == intent.intent_hash


def test_every_archetype_renders_its_signature_resource() -> None:
    signatures = {
        Archetype.PAYMENTS_API: "aws_db_instance.cardholder",
        Archetype.CUSTOMER_DATA_PLATFORM: "aws_glue_catalog_database.pii",
        Archetype.INTERNAL_REPORTING: "aws_instance.reporting",
    }
    for archetype, signature in signatures.items():
        estate = render_estate(_intent(2, archetype), 9)
        assert signature in estate.resource_addresses


def test_resource_addresses_are_unique() -> None:
    estate = render_estate(_intent(11), 4)
    addresses = estate.resource_addresses
    assert len(addresses) == len(set(addresses))


def test_all_references_point_at_real_resources() -> None:
    # No reference may dangle — every referenced address must exist in the estate.
    for seed in range(15):
        estate = render_estate(_intent(seed), seed)
        addresses = set(estate.resource_addresses)
        for res in estate.resources:
            for ref in res.references:
                assert ref in addresses, f"{res.address} -> missing {ref}"


def test_terraform_json_is_well_formed() -> None:
    estate = render_estate(_intent(1, Archetype.PAYMENTS_API), 1)
    tf = estate.to_terraform_json()
    assert tf["terraform"]["required_providers"]["aws"]["source"] == "hashicorp/aws"
    assert tf["provider"]["aws"]["region"] == estate.region

    resource_block = tf["resource"]
    assert "aws_vpc" in resource_block
    # No internal __ref__ markers leak into the rendered config.
    for by_name in resource_block.values():
        for body in by_name.values():
            assert not any(k.startswith("__ref__") for k in body)


def test_terraform_json_renders_references_as_interpolations() -> None:
    estate = render_estate(_intent(1, Archetype.PAYMENTS_API), 1)
    subnet_blocks = estate.to_terraform_json()["resource"].get("aws_subnet", {})
    # Every subnet must interpolate the VPC id on its vpc_id argument.
    assert subnet_blocks  # payments API always has subnets
    for body in subnet_blocks.values():
        assert body["vpc_id"] == "${aws_vpc.main.id}"
