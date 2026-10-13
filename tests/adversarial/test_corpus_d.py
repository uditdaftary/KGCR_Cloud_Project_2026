"""Corpus D: licences are checked before anything counts, the HCL shape is normalised so the
rule floor can read it, and the agreement counts are what they say.

No network and no third-party repository is needed: HCL is written to a temp directory and
Checkov's output is a small canned document.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("hcl2")

from kgcr.adversarial.acquire import REPOSITORIES, detect_licence  # noqa: E402
from kgcr.adversarial.evaluate import FAMILIES, evaluate, parse_results  # noqa: E402
from kgcr.adversarial.hcl import load_hcl_directory  # noqa: E402
from kgcr.defects.adversarial import ACCEPTED_LICENCES, AdversarialArtifact  # noqa: E402

APACHE = (
    "                                 Apache License\n"
    "                           Version 2.0, January 2004\n"
)
BSD3 = "BSD 3-Clause License\n\nCopyright (c) 2018, Someone\nAll rights reserved.\n"
MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy"
GPL = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"


@pytest.mark.parametrize(
    ("text", "expected"),
    [(APACHE, "Apache-2.0"), (BSD3, "BSD-3-Clause"), (MIT, "MIT"), (GPL, None), ("", None)],
)
def test_licence_texts_are_recognised_or_refused(text: str, expected: str | None) -> None:
    assert detect_licence(text) == expected


def test_an_unaccepted_licence_cannot_be_registered() -> None:
    assert "GPL-3.0" not in ACCEPTED_LICENCES
    with pytest.raises(ValueError, match="non-permissive"):
        AdversarialArtifact("x", "s", "GPL-3.0", "https://example.test/x.git", "abc")
    with pytest.raises(ValueError, match="provenance"):
        AdversarialArtifact("x", "s", "MIT", "", "")


def test_the_sources_named_are_the_two_public_repositories() -> None:
    assert [(r[0], r[1]) for r in REPOSITORIES] == [
        ("terragoat", "https://github.com/bridgecrewio/terragoat.git"),
        ("cloudgoat", "https://github.com/RhinoSecurityLabs/cloudgoat.git"),
    ]


HCL = """
resource "aws_security_group" "web" {
  name = "web"
  ingress {
    from_port   = 80
    to_port     = 80
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "closed" {
  ingress {
    from_port   = 443
    cidr_blocks = ["10.0.0.0/8"]
  }
}
resource "aws_db_instance" "plain" {
  engine            = "postgres"
  storage_encrypted = false
}
resource "aws_db_instance" "unresolved" {
  engine            = "postgres"
  storage_encrypted = var.encrypt
}
resource "aws_ebs_volume" "vol" {
  size      = 1
  encrypted = true
}
resource "azurerm_thing" "ignored" {
  name = "not aws"
}
"""


def _parsed(tmp_path: Path):  # type: ignore[no-untyped-def]
    (tmp_path / "main.tf").write_text(HCL, encoding="utf-8")
    return load_hcl_directory(tmp_path)


def test_the_parser_shape_is_unwrapped_and_blocks_stay_lists(tmp_path: Path) -> None:
    parsed = _parsed(tmp_path)
    by_address = {r.address: r for r in parsed.resources}
    assert "azurerm_thing.ignored" not in by_address  # only aws_* resources are kept
    web = by_address["aws_security_group.web"].attributes
    assert web["ingress"] == [{"from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]}]
    assert by_address["aws_db_instance.plain"].attributes["storage_encrypted"] is False
    assert by_address["aws_ebs_volume.vol"].attributes["encrypted"] is True
    assert "__start_line__" not in web


def test_an_unparseable_file_is_reported_not_fatal_and_not_silent(tmp_path: Path) -> None:
    (tmp_path / "good.tf").write_text(HCL, encoding="utf-8")
    (tmp_path / "bad.tf").write_text('resource "aws_x" "y" {{{ not hcl', encoding="utf-8")
    parsed = load_hcl_directory(tmp_path)
    assert parsed.files == 2 and len(parsed.skipped) == 1 and parsed.skipped[0].startswith("bad.tf")
    assert parsed.resources  # the good file still counts


CHECKOV = {
    "results": {
        "failed_checks": [
            {
                "check_id": "CKV_AWS_260",
                "resource": "aws_security_group.web",
                "file_path": "/main.tf",
            },
            {
                "check_id": "CKV_AWS_16",
                "resource": "aws_db_instance.plain",
                "file_path": "/main.tf",
            },
            {
                "check_id": "CKV_AWS_16",
                "resource": "aws_db_instance.unresolved",
                "file_path": "/main.tf",
            },
            {"check_id": "CKV_AWS_999", "resource": "aws_s3_bucket.other", "file_path": "/main.tf"},
        ],
        "passed_checks": [
            {"check_id": "CKV_AWS_3", "resource": "aws_ebs_volume.vol", "file_path": "/main.tf"}
        ],
    }
}


def test_agreement_counts_and_the_blind_spot_are_reported_separately(tmp_path: Path) -> None:
    parsed = _parsed(tmp_path)
    report = evaluate([parsed], parse_results(CHECKOV), tmp_path)
    fams = {f["family"]: f for f in report["families"]}
    ingress = fams["open_ingress"]
    assert (
        ingress["both_flag"],
        ingress["neither_flags"],
        ingress["resources_of_these_types"],
    ) == (1, 1, 2)
    db = fams["unencrypted_database"]
    # `plain` is flagged by both; `unresolved` is flagged by the rule floor too, because
    # storage_encrypted is not literally true, so the blind spot here is empty.
    assert db["both_flag"] == 2 and db["only_checkov_flags"] == 0
    assert fams["unencrypted_volume"]["neither_flags"] == 1
    assert report["coverage"]["checkov_failed_checks"] == 4
    assert report["coverage"]["in_rule_floor_families"] == 3
    assert report["coverage"]["most_common_outside"] == [{"check_id": "CKV_AWS_999", "count": 1}]


def test_an_unresolved_expression_the_rule_cannot_read_is_counted_as_a_blind_spot(
    tmp_path: Path,
) -> None:
    # Checkov fails a bucket whose ACL is a variable; the rule floor cannot read it.
    (tmp_path / "main.tf").write_text(
        'resource "aws_s3_bucket" "b" {\n  acl = var.acl\n}\n', encoding="utf-8"
    )
    data = {
        "results": {
            "failed_checks": [
                {"check_id": "CKV_AWS_20", "resource": "aws_s3_bucket.b", "file_path": "/main.tf"}
            ]
        }
    }
    report = evaluate([load_hcl_directory(tmp_path)], parse_results(data), tmp_path)
    family = next(f for f in report["families"] if f["family"] == "public_bucket_acl")
    assert family["only_checkov_flags"] == 1 and family["missed_because_unresolved_expression"] == 1
    assert family["recall_against_checkov"] == 0.0


def test_every_family_maps_to_a_rule_the_floor_actually_has() -> None:
    from kgcr.corpus.resources import Resource
    from kgcr.defects.detectors import resource_findings

    probes = [
        Resource("aws_security_group", "p", {"ingress": [{"cidr_blocks": ["0.0.0.0/0"]}]}),
        Resource("aws_db_instance", "p", {"publicly_accessible": True, "storage_encrypted": False}),
        Resource("aws_s3_bucket", "p", {"acl": "public-read"}),
        Resource("aws_ebs_volume", "p", {}),
        Resource(
            "aws_iam_policy",
            "p",
            {"policy": '{"Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'},
        ),
        Resource("aws_cloudtrail", "p", {}),
    ]
    raised = {f.rule_id for res in probes for f in resource_findings(res)}
    assert set().union(*(f.ours for f in FAMILIES)) <= raised
