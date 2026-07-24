"""The single-resource oracle is clean on the compliant corpus; the traversal works."""

from __future__ import annotations

from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import Archetype
from kgcr.corpus.resources import Resource
from kgcr.corpus.sampler import IntentSampler
from kgcr.defects.detectors import relational_path_exists, single_resource_findings


def _clean(seed: int, archetype: Archetype | None = None):
    return render_estate(IntentSampler(seed).sample(archetype), seed)


def test_oracle_is_silent_on_the_clean_corpus() -> None:
    # If the oracle fired on compliant estates it would be worthless as a gate;
    # every clean estate across archetypes and seeds must score zero.
    for seed in range(25):
        estate = _clean(seed)
        assert single_resource_findings(estate) == [], f"false positive on seed {seed}"


def test_scoped_iam_policy_is_not_flagged_but_wildcard_is() -> None:
    # The clean generator uses a scoped resource ("arn:aws:s3:::kgcr-*/*") which
    # contains a '*' but is not '*': it must not trip. A true wildcard must.
    estate = _clean(1, Archetype.PAYMENTS_API)
    assert single_resource_findings(estate) == []

    wild = Resource(
        "aws_iam_role_policy",
        "bad",
        {"policy": '{"Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'},
    )
    estate2 = estate.__class__(
        estate_id="x",
        intent=estate.intent,
        resources=(*estate.resources, wild),
        seed=estate.seed,
        seed_family=estate.seed_family,
        region=estate.region,
    )
    findings = single_resource_findings(estate2)
    assert any(f.address == "aws_iam_role_policy.bad" for f in findings)


def test_open_ingress_and_public_flags_are_caught() -> None:
    estate = _clean(2, Archetype.PAYMENTS_API)
    sg = Resource(
        "aws_security_group",
        "open",
        {"ingress": [{"cidr_blocks": ["0.0.0.0/0"]}]},
    )
    pub = Resource("aws_db_instance", "leaky", {"publicly_accessible": True})
    estate2 = estate.__class__(
        estate_id="x",
        intent=estate.intent,
        resources=(*estate.resources, sg, pub),
        seed=estate.seed,
        seed_family=estate.seed_family,
        region=estate.region,
    )
    rules = {f.rule_id for f in single_resource_findings(estate2)}
    assert "CKV_AWS_260" in rules
    assert "CKV_AWS_17" in rules


def test_relational_path_absent_between_isolated_resources() -> None:
    # In a clean estate the sensitive DB connects only to the KMS key, so no
    # short path exists to the internet gateway — the DF-7 defect is what
    # creates one.
    estate = _clean(3, Archetype.PAYMENTS_API)
    if "aws_internet_gateway.igw" in estate.resource_addresses:
        assert (
            relational_path_exists(
                estate, "aws_db_instance.cardholder", "aws_internet_gateway.igw", hop_bound=3
            )
            is None
        )


def test_relational_path_respects_the_hop_bound() -> None:
    estate = _clean(4, Archetype.PAYMENTS_API)
    # A resource reaches itself in zero hops.
    self_path = relational_path_exists(estate, "aws_vpc.main", "aws_vpc.main", hop_bound=3)
    assert self_path == ("aws_vpc.main",)
