"""The preflight refuses a plan the write role cannot carry out, and cannot drift from the
Terraform that defines the role."""

from __future__ import annotations

import re
from pathlib import Path

from kgcr.apply.preflight import ALLOWED_SERVICES_DEFAULT, allowed_services, check, service_for
from kgcr.corpus.pipeline import generate_corpus

ROOT = Path(__file__).resolve().parents[2]


def test_the_shipped_grant_refuses_a_database() -> None:
    assert check(["aws_vpc", "aws_db_instance"], ALLOWED_SERVICES_DEFAULT) == [
        "aws_db_instance (needs rds)"
    ]


def test_a_declared_widening_is_honoured() -> None:
    services = allowed_services({"KGCR_PROVISION_SERVICES": " EC2, s3 ,rds "})
    assert services == ("ec2", "rds", "s3")
    assert check(["aws_db_instance", "aws_vpc"], services) == []


def test_an_unset_declaration_is_the_shipped_default() -> None:
    assert allowed_services({}) == ALLOWED_SERVICES_DEFAULT
    assert allowed_services({"KGCR_PROVISION_SERVICES": "  "}) == ALLOWED_SERVICES_DEFAULT


def test_an_unknown_type_is_refused_not_assumed_safe() -> None:
    assert check(["aws_made_up"], ["ec2", "s3"]) == [
        "aws_made_up (service unknown to the preflight)"
    ]


def test_every_type_a_generated_estate_holds_is_mapped() -> None:
    types = {r.type for e in generate_corpus(60, 1729) for r in e.resources}
    assert {t: service_for(t) for t in types}  # raises KeyError for any unmapped type


def test_the_default_matches_the_terraform_that_defines_the_role() -> None:
    variables = (ROOT / "src" / "aws" / "variables.tf").read_text(encoding="utf-8")
    block = variables[variables.index('variable "provision_services"') :]
    default = re.search(r"default\s*=\s*\[(.*?)\]", block, re.S)
    assert default, "provision_services needs a default"
    declared = tuple(re.findall(r'"([^"]+)"', default.group(1)))
    assert declared == ALLOWED_SERVICES_DEFAULT
    policy = (ROOT / "src" / "aws" / "iam_cross_account.tf").read_text(encoding="utf-8")
    assert "var.provision_services" in policy and '"ec2:*"' not in policy
