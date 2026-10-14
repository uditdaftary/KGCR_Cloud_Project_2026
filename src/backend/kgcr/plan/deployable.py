"""A Terraform document that real Terraform accepts, built from an estate.

``Estate.to_terraform_json`` is valid Terraform JSON *syntax*, but the generator models what
the detectors read, not what the AWS provider requires: ``terraform validate`` rejects it
(a load balancer with no subnets, an encryption configuration with no rule). This module
completes those required arguments at render time and **reports every completion**, so the
reviewed spec and the document handed to Terraform can be compared. The corpus, its hashes
and every recorded fixture are untouched.

Completions use the least exposed choice (a database goes in private subnets, an internal
load balancer in private subnets). They make a plan validate. They do not make an apply
succeed: whatever else a real account needs (bucket policy for CloudTrail, routes, an AMI
valid in the region) is listed as a caveat, not invented.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from kgcr.hashing import canonical_hash

__all__ = ["PLACEHOLDER_AMI", "OverlaidDocument", "document_hash", "terraform_document"]

# Not a real image. A document carrying it can be planned, never applied (see apply).
PLACEHOLDER_AMI = "ami-00000000000000000"
_AZ_LETTERS = "abc"
_RULE_DEFAULTS: dict[str, Any] = {
    "description": "",
    "cidr_blocks": [],
    "ipv6_cidr_blocks": [],
    "prefix_list_ids": [],
    "security_groups": [],
    "self": False,
}
_OFFLINE_PROVIDER = {
    "access_key": "mock",
    "secret_key": "mock",
    "skip_credentials_validation": True,
    "skip_requesting_account_id": True,
    "skip_metadata_api_check": True,
    "skip_region_validation": True,
}


@dataclass(frozen=True, slots=True)
class OverlaidDocument:
    document: dict[str, Any]
    overlay: tuple[str, ...]  # what was added beyond the reviewed spec
    caveats: tuple[str, ...]  # why a valid plan may still fail to apply


def document_hash(spec: Mapping[str, Any]) -> str:
    """Identity of a Terraform document, ignoring the provider block (credentials live there)."""
    return canonical_hash({k: v for k, v in spec.items() if k != "provider"})


def _ref(address: str, attr: str = "id") -> str:
    return "${" + f"{address}.{attr}" + "}"


def terraform_document(spec: Mapping[str, Any], *, offline: bool) -> OverlaidDocument:
    """A spec's Terraform JSON (``Estate.to_terraform_json``) with required arguments completed.

    ``offline`` adds mock keys and skips every provider call, so ``terraform plan`` needs no
    AWS account. Without it the provider block carries the region only and credentials come
    from the environment of whoever applies.
    """
    doc = copy.deepcopy(dict(spec))
    region = doc["provider"]["aws"]["region"]
    resources: dict[str, dict[str, dict[str, Any]]] = doc.setdefault("resource", {})
    overlay: list[str] = []
    caveats: list[str] = []
    if offline:
        doc["provider"]["aws"].update(_OFFLINE_PROVIDER)
        overlay.append("provider aws: mock credentials and skipped provider calls (offline plan)")

    subnets = resources.get("aws_subnet", {})
    public = [n for n, b in sorted(subnets.items()) if b.get("map_public_ip_on_launch") is True]
    private = [n for n, b in sorted(subnets.items()) if b.get("map_public_ip_on_launch") is False]

    for name, body in subnets.items():
        match = re.search(r"(\d+)$", name)
        letter = _AZ_LETTERS[(int(match.group(1)) if match else 0) % len(_AZ_LETTERS)]
        body["availability_zone"] = f"{region}{letter}"
        overlay.append(f"aws_subnet.{name}: availability_zone = {body['availability_zone']}")

    for name, body in resources.get(
        "aws_s3_bucket_server_side_encryption_configuration", {}
    ).items():
        keys = sorted(resources.get("aws_kms_key", {}))
        default: dict[str, Any] = (
            {"sse_algorithm": "aws:kms", "kms_master_key_id": _ref(f"aws_kms_key.{keys[0]}", "arn")}
            if keys
            else {"sse_algorithm": "AES256"}
        )
        body["rule"] = [{"apply_server_side_encryption_by_default": default}]
        overlay.append(
            f"aws_s3_bucket_server_side_encryption_configuration.{name}: "
            f"rule = {default['sse_algorithm']}"
        )

    for name, body in resources.get("aws_lb", {}).items():
        wanted = private if body.get("internal") else public
        chosen = wanted or sorted(subnets)
        body["subnets"] = [_ref(f"aws_subnet.{n}") for n in chosen]
        groups = [r for r in body.get("depends_on", []) if r.startswith("aws_security_group.")]
        if groups:
            body["security_groups"] = [_ref(g) for g in groups]
        overlay.append(f"aws_lb.{name}: subnets = {', '.join(chosen) or 'none'}")
        zones = {subnets[n]["availability_zone"] for n in chosen}
        if len(zones) < 2:
            caveats.append(
                f"aws_lb.{name}: subnets span {len(zones)} zone; a load balancer needs two"
            )

    for name, body in resources.get("aws_db_instance", {}).items():
        body["username"] = "kgcr_admin"
        body["manage_master_user_password"] = True
        body["skip_final_snapshot"] = True
        overlay.append(
            f"aws_db_instance.{name}: username, manage_master_user_password (no password in the "
            "document), skip_final_snapshot = true so a teardown does not leave a snapshot"
        )
        chosen = private or sorted(subnets)
        if chosen:
            resources.setdefault("aws_db_subnet_group", {})["kgcr"] = {
                "name": "kgcr-db",
                "subnet_ids": [_ref(f"aws_subnet.{n}") for n in chosen],
            }
            body["db_subnet_group_name"] = _ref("aws_db_subnet_group.kgcr", "name")
            overlay.append(f"aws_db_subnet_group.kgcr: added, subnets = {', '.join(chosen)}")
            if len({subnets[n]["availability_zone"] for n in chosen}) < 2:
                caveats.append(
                    f"aws_db_instance.{name}: its subnet group spans one zone; RDS needs two"
                )

    for name, body in resources.get("aws_instance", {}).items():
        body["ami"] = "${var.ami_id}"
        doc.setdefault("variable", {})["ami_id"] = {
            "type": "string",
            "default": PLACEHOLDER_AMI,
            "description": "Image for aws_instance. The default is a placeholder: set a real "
            "image for the region before any apply.",
        }
        overlay.append(f"aws_instance.{name}: ami = var.ami_id (placeholder {PLACEHOLDER_AMI})")
        caveats.append(f"aws_instance.{name}: the image is a placeholder and must be replaced")

    for name, body in resources.get("aws_security_group", {}).items():
        # The provider models ingress/egress as attributes, so every element must carry every
        # key; absent ones take the empty value, which changes no rule.
        for direction in ("ingress", "egress"):
            rules = body.get(direction)
            if not isinstance(rules, list):
                continue
            body[direction] = [
                {**_RULE_DEFAULTS, **rule} for rule in rules if isinstance(rule, dict)
            ]
            overlay.append(f"aws_security_group.{name}: {direction} rule keys completed")

    for name in resources.get("aws_cloudtrail", {}):
        caveats.append(f"aws_cloudtrail.{name}: needs a bucket policy that lets CloudTrail write")
    if public and "aws_internet_gateway" in resources:
        caveats.append("public subnets have no route table to the internet gateway")
    return OverlaidDocument(doc, tuple(overlay), tuple(caveats))
