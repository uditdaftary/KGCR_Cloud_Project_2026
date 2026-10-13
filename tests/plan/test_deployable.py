"""The overlay completes what the AWS provider requires, reports every addition, and does
not touch the reviewed spec."""

from __future__ import annotations

import itertools

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import Archetype, AZSpread, NetworkLayout
from kgcr.design.intake import build_intent
from kgcr.plan.deployable import PLACEHOLDER_AMI, terraform_document


def _estate(archetype: str, az: str, layout: str, region: str = "eu-west-1"):  # type: ignore[no-untyped-def]
    return render_estate(
        build_intent(
            {
                "archetype": archetype,
                "region": region,
                "az_spread": az,
                "network_layout": layout,
                "logging": "full",
                "iam_shape": "least_privilege",
                "tagging": "strict",
                "scale": "small",
            }
        ),
        1729,
    )


COMBOS = list(
    itertools.product(
        [a.value for a in Archetype], [a.value for a in AZSpread], [n.value for n in NetworkLayout]
    )
)


@pytest.mark.parametrize(("archetype", "az", "layout"), COMBOS)
def test_required_arguments_are_completed_for_every_intent(
    archetype: str, az: str, layout: str
) -> None:
    estate = _estate(archetype, az, layout)
    out = terraform_document(estate.to_terraform_json(), offline=True)
    res = out.document["resource"]
    for body in res.get("aws_subnet", {}).values():
        assert body["availability_zone"].startswith("eu-west-1")
    for body in res.get("aws_lb", {}).values():
        assert body["subnets"], "a load balancer needs subnets"
    for body in res.get("aws_s3_bucket_server_side_encryption_configuration", {}).values():
        assert body["rule"][0]["apply_server_side_encryption_by_default"]["sse_algorithm"]
    for body in res.get("aws_db_instance", {}).values():
        assert body["username"] and body["manage_master_user_password"] is True
        assert "password" not in body  # never a password in a document
        assert "aws_db_subnet_group" in res
    for body in res.get("aws_instance", {}).values():
        assert body["ami"] == "${var.ami_id}"
        assert out.document["variable"]["ami_id"]["default"] == PLACEHOLDER_AMI
    assert out.overlay and all(isinstance(o, str) for o in out.overlay)


def test_the_overlay_never_mutates_the_reviewed_spec() -> None:
    estate = _estate("payments_api", "two_az", "public_private")
    before = estate.to_terraform_json()
    terraform_document(estate.to_terraform_json(), offline=True)
    assert estate.to_terraform_json() == before
    assert (
        "rule"
        not in before["resource"]["aws_s3_bucket_server_side_encryption_configuration"]["logs"]
    )


def test_offline_adds_mock_credentials_and_online_does_not() -> None:
    estate = _estate("payments_api", "two_az", "public_private")
    offline = terraform_document(estate.to_terraform_json(), offline=True).document["provider"][
        "aws"
    ]
    online = terraform_document(estate.to_terraform_json(), offline=False).document["provider"][
        "aws"
    ]
    assert offline["access_key"] == "mock" and offline["skip_credentials_validation"] is True
    assert online == {"region": "eu-west-1"}


def test_an_internal_load_balancer_goes_in_private_subnets_an_external_one_in_public() -> None:
    estate = _estate("payments_api", "two_az", "public_private")
    out = terraform_document(estate.to_terraform_json(), offline=False)
    lb = next(iter(out.document["resource"]["aws_lb"].values()))
    subnets = out.document["resource"]["aws_subnet"]
    wanted = lb["internal"] is False
    for ref in lb["subnets"]:
        name = ref.removeprefix("${aws_subnet.").removesuffix(".id}")
        assert subnets[name]["map_public_ip_on_launch"] is wanted


def test_a_single_zone_estate_gets_a_caveat_not_a_silent_pass() -> None:
    out = terraform_document(
        _estate("payments_api", "single_az", "public_private").to_terraform_json(), offline=True
    )
    assert any("needs two" in c for c in out.caveats)


def test_the_database_lands_in_private_subnets_and_keeps_its_encryption() -> None:
    estate = _estate("payments_api", "two_az", "public_private")
    res = terraform_document(estate.to_terraform_json(), offline=True).document["resource"]
    group = res["aws_db_subnet_group"]["kgcr"]["subnet_ids"]
    assert group and all("private" in ref for ref in group)
    db = next(iter(res["aws_db_instance"].values()))
    assert db["storage_encrypted"] is True and db["publicly_accessible"] is False


def test_the_overlay_is_deterministic() -> None:
    estate = _estate("customer_data_platform", "three_az", "private_with_nat")
    assert terraform_document(estate.to_terraform_json(), offline=True) == terraform_document(
        estate.to_terraform_json(), offline=True
    )


def test_a_security_group_rule_gets_every_key_the_provider_requires_and_keeps_its_meaning() -> None:
    estate = _estate("payments_api", "two_az", "public_private")
    spec = estate.to_terraform_json()
    group = next(iter(spec["resource"]["aws_security_group"].values()))
    group["ingress"] = [
        {"from_port": 22, "to_port": 22, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]}
    ]
    out = terraform_document(spec, offline=True)
    rule = next(iter(out.document["resource"]["aws_security_group"].values()))["ingress"][0]
    assert rule["cidr_blocks"] == ["0.0.0.0/0"] and rule["from_port"] == 22
    assert rule["self"] is False and rule["security_groups"] == [] and rule["description"] == ""
    assert any("ingress rule keys completed" in o for o in out.overlay)
    assert group["ingress"][0].keys() == {"from_port", "to_port", "protocol", "cidr_blocks"}
