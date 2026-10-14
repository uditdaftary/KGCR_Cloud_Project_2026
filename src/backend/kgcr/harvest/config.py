"""Harvest an account's resources from AWS Config into the estate IR (read-only).

Calls two Config APIs through an injected client: ``list_discovered_resources`` to find
resources and ``batch_get_resource_config`` (100 keys a call) to read them. Field names come
from the AWS Config resource schema (awslabs/aws-config-resource-schema); nothing is guessed.

What a harvest is not, stated so a reader cannot take more from it than it holds:

* **Five resource types only.** VPCs, subnets, route tables, IAM, load balancers and the rest
  are not read, so the relational defects (internet reachability, privilege escalation, trust
  chains) cannot be evaluated from a harvest until those types are added.
* **No tags.** ``BatchGetResourceConfig`` strips them. A harvested estate reads as untagged.
* **Deleted and unrecorded resources are listed as skipped,** never dropped silently.
* An attribute Config does not report is left out, not set false: the rule floor reads an
  absent encryption flag as a finding, so a gap in Config shows up as one rather than as a pass.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from kgcr.corpus.resources import Resource

__all__ = ["ConfigClient", "Harvest", "Skipped", "SUPPORTED_TYPES", "harvest_account"]

BATCH_LIMIT = 100  # BatchGetResourceConfig accepts at most 100 resource keys


class ConfigClient(Protocol):
    """The two calls of a boto3 ``config`` client that a harvest makes."""

    def list_discovered_resources(self, **kwargs: Any) -> dict[str, Any]: ...

    def batch_get_resource_config(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Skipped:
    resource_type: str
    resource_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class Harvest:
    resources: tuple[Resource, ...]
    account_id: str | None
    region: str
    skipped: tuple[Skipped, ...]
    caveats: tuple[str, ...]


@dataclass(slots=True)
class _Draft:
    """A resource under construction: ids that point at other harvested resources, unresolved."""

    resource: Resource
    config_id: str  # the id other resources use for this one (group id, key id, bucket name)
    # (argument, kind, value): kind is "sg" or "kms"; resolved once every resource is known.
    links: tuple[tuple[str, str, str], ...] = ()


def _clean(attrs: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in attrs.items() if v is not None}


def _decode(value: Any) -> Any:
    """Config sends JSON inside JSON strings; some emulators encode twice."""
    for _ in range(2):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value)
        except ValueError:
            break
    return value


def _rules(permissions: Any) -> list[dict[str, Any]]:
    """Config ``ipPermissions`` as Terraform ``ingress``/``egress`` rule blocks."""
    out: list[dict[str, Any]] = []
    for perm in permissions or []:
        cidrs = [r["cidrIp"] for r in perm.get("ipv4Ranges", []) if r.get("cidrIp")]
        cidrs += [c for c in perm.get("ipRanges", []) if isinstance(c, str) and c not in cidrs]
        v6 = [r["cidrIpv6"] for r in perm.get("ipv6Ranges", []) if r.get("cidrIpv6")]
        groups = [p["groupId"] for p in perm.get("userIdGroupPairs", []) if p.get("groupId")]
        out.append(
            _clean(
                {
                    "from_port": perm.get("fromPort"),
                    "to_port": perm.get("toPort"),
                    "protocol": perm.get("ipProtocol"),
                    "cidr_blocks": cidrs,
                    "ipv6_cidr_blocks": v6 or None,
                    "security_groups": groups or None,
                }
            )
        )
    return out


def _rds(name: str, cfg: Mapping[str, Any], supp: Mapping[str, Any]) -> list[_Draft]:
    links = [
        ("vpc_security_group_ids", "sg", g["vpcSecurityGroupId"])
        for g in cfg.get("vpcSecurityGroups", [])
        if g.get("vpcSecurityGroupId")
    ]
    if cfg.get("kmsKeyId"):
        links.append(("kms_key_id", "kms", cfg["kmsKeyId"]))
    attrs = _clean(
        {
            "identifier": cfg.get("dBInstanceIdentifier"),
            "engine": cfg.get("engine"),
            "instance_class": cfg.get("dBInstanceClass"),
            "allocated_storage": cfg.get("allocatedStorage"),
            "storage_encrypted": cfg.get("storageEncrypted"),
            "publicly_accessible": cfg.get("publiclyAccessible"),
            "multi_az": cfg.get("multiAZ"),
            "backup_retention_period": cfg.get("backupRetentionPeriod"),
            "deletion_protection": cfg.get("deletionProtection"),
            "iam_database_authentication_enabled": cfg.get("iAMDatabaseAuthenticationEnabled"),
        }
    )
    return [
        _Draft(
            Resource("aws_db_instance", name, attrs),
            cfg.get("dBInstanceIdentifier", ""),
            tuple(links),
        )
    ]


def _security_group(name: str, cfg: Mapping[str, Any], supp: Mapping[str, Any]) -> list[_Draft]:
    attrs = _clean(
        {
            "name": cfg.get("groupName"),
            "description": cfg.get("description"),
            "vpc_id": cfg.get("vpcId"),
            "ingress": _rules(cfg.get("ipPermissions")),
            "egress": _rules(cfg.get("ipPermissionsEgress")),
        }
    )
    return [_Draft(Resource("aws_security_group", name, attrs), cfg.get("groupId", ""))]


def _instance(name: str, cfg: Mapping[str, Any], supp: Mapping[str, Any]) -> list[_Draft]:
    links = [
        ("vpc_security_group_ids", "sg", g["groupId"])
        for g in cfg.get("securityGroups", [])
        if g.get("groupId")
    ]
    meta = cfg.get("metadataOptions") or {}
    attrs = _clean(
        {
            "ami": cfg.get("imageId"),
            "instance_type": cfg.get("instanceType"),
            "subnet_id": cfg.get("subnetId"),
            "associate_public_ip_address": bool(cfg.get("publicIpAddress")),
            "ebs_optimized": cfg.get("ebsOptimized"),
            "metadata_options": _clean(
                {
                    "http_tokens": meta.get("httpTokens"),
                    "http_endpoint": meta.get("httpEndpoint"),
                    "http_put_response_hop_limit": meta.get("httpPutResponseHopLimit"),
                }
            )
            or None,
        }
    )
    return [_Draft(Resource("aws_instance", name, attrs), cfg.get("instanceId", ""), tuple(links))]


def _kms(name: str, cfg: Mapping[str, Any], supp: Mapping[str, Any]) -> list[_Draft]:
    attrs = _clean(
        {
            "description": cfg.get("description"),
            "is_enabled": cfg.get("enabled"),
            "key_usage": cfg.get("keyUsage"),
            "multi_region": cfg.get("multiRegion"),
        }
    )
    return [_Draft(Resource("aws_kms_key", name, attrs), cfg.get("keyId", ""))]


def _bucket(name: str, cfg: Mapping[str, Any], supp: Mapping[str, Any]) -> list[_Draft]:
    bucket_name = cfg.get("name", "")
    address = f"aws_s3_bucket.{name}"
    drafts = [_Draft(Resource("aws_s3_bucket", name, {"bucket": bucket_name}), bucket_name)]
    ref = {"__ref__bucket": address}
    public = _decode(supp.get("PublicAccessBlockConfiguration"))
    if isinstance(public, dict):
        attrs = _clean(
            {
                "block_public_acls": public.get("blockPublicAcls"),
                "block_public_policy": public.get("blockPublicPolicy"),
                "ignore_public_acls": public.get("ignorePublicAcls"),
                "restrict_public_buckets": public.get("restrictPublicBuckets"),
            }
        )
        drafts.append(
            _Draft(
                Resource("aws_s3_bucket_public_access_block", name, {**ref, **attrs}, (address,)),
                "",
            )
        )
    sse = _decode(supp.get("ServerSideEncryptionConfiguration"))
    rules = sse.get("rules") if isinstance(sse, dict) else None
    rules = [rules] if isinstance(rules, dict) else rules
    if isinstance(rules, list) and rules:
        default = (rules[0] or {}).get("applyServerSideEncryptionByDefault") or {}
        block = _clean(
            {
                "sse_algorithm": default.get("sseAlgorithm"),
                "kms_master_key_id": default.get("kmsMasterKeyID"),
            }
        )
        drafts.append(
            _Draft(
                Resource(
                    "aws_s3_bucket_server_side_encryption_configuration",
                    name,
                    {**ref, "rule": [{"apply_server_side_encryption_by_default": block}]},
                    (address,),
                ),
                "",
            )
        )
    return drafts


_Mapper = Callable[[str, Mapping[str, Any], Mapping[str, Any]], list[_Draft]]
_MAPPERS: dict[str, _Mapper] = {
    "AWS::RDS::DBInstance": _rds,
    "AWS::S3::Bucket": _bucket,
    "AWS::EC2::SecurityGroup": _security_group,
    "AWS::EC2::Instance": _instance,
    "AWS::KMS::Key": _kms,
}
SUPPORTED_TYPES = tuple(_MAPPERS)

_NOT_READABLE = ("ResourceNotRecorded", "ResourceDeleted", "ResourceDeletedNotRecorded")


def _discover(client: ConfigClient, resource_type: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"resourceType": resource_type}
        if token:
            kwargs["nextToken"] = token
        page = client.list_discovered_resources(**kwargs)
        found.extend(page.get("resourceIdentifiers", []))
        token = page.get("nextToken")
        if not token:
            return found


def _address_name(item: Mapping[str, Any], taken: set[str]) -> str:
    raw = item.get("resourceName") or item.get("resourceId") or "resource"
    name = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw))
    if not re.match(r"[A-Za-z_]", name):
        name = f"r_{name}"
    if name in taken:  # two resources of one type can share a Name tag or be unnamed
        name = f"{name}_{re.sub(r'[^A-Za-z0-9]', '', str(item.get('resourceId')))[-8:]}"
    taken.add(name)
    return name


def harvest_account(client: ConfigClient, *, region: str) -> Harvest:
    """Read every supported resource Config knows in this region; never writes."""
    skipped: list[Skipped] = []
    drafts: list[_Draft] = []
    account: str | None = None
    for resource_type, mapper in _MAPPERS.items():
        ids = [i["resourceId"] for i in _discover(client, resource_type)]
        taken: set[str] = set()
        for start in range(0, len(ids), BATCH_LIMIT):
            keys = [
                {"resourceType": resource_type, "resourceId": i}
                for i in ids[start : start + BATCH_LIMIT]
            ]
            reply = client.batch_get_resource_config(resourceKeys=keys)
            for key in reply.get("unprocessedResourceKeys", []):
                skipped.append(Skipped(resource_type, key["resourceId"], "not processed by Config"))
            for item in reply.get("baseConfigurationItems", []):
                rid = str(item.get("resourceId"))
                if item.get("configurationItemStatus") in _NOT_READABLE or not item.get(
                    "configuration"
                ):
                    status = item.get("configurationItemStatus") or "no configuration"
                    skipped.append(
                        Skipped(resource_type, rid, f"no readable configuration: {status}")
                    )
                    continue
                cfg = _decode(item["configuration"])
                supp = item.get("supplementaryConfiguration") or {}
                if resource_type == "AWS::KMS::Key" and cfg.get("keyManager") == "AWS":
                    skipped.append(Skipped(resource_type, rid, "AWS-managed key"))
                    continue
                account = account or item.get("accountId")
                drafts.extend(mapper(_address_name(item, taken), cfg, supp))
    return Harvest(
        resources=_resolve(drafts),
        account_id=account,
        region=region,
        skipped=tuple(skipped),
        caveats=(
            "Only RDS instances, S3 buckets, security groups, EC2 instances and KMS keys are read;"
            " networks, IAM and load balancers are not, so relational defects cannot be evaluated.",
            "Config's batch read returns no tags: the harvested estate reads as untagged.",
            "KMS key rotation is not in the Config item: it is left unset, not assumed.",
        ),
    )


def _resolve(drafts: list[_Draft]) -> tuple[Resource, ...]:
    """Turn ids that name another harvested resource into references; keep the rest literal."""
    index = {
        ("sg", d.config_id): d.resource.address
        for d in drafts
        if d.resource.type == "aws_security_group" and d.config_id
    }
    for d in drafts:
        if d.resource.type == "aws_kms_key" and d.config_id:
            index[("kms", d.config_id)] = d.resource.address
    out: list[Resource] = []
    for d in drafts:
        attrs = dict(d.resource.attributes)
        references = list(d.resource.references)
        unresolved: dict[str, list[str]] = {}
        for argument, kind, value in d.links:
            target = index.get((kind, value)) or index.get((kind, value.rsplit("/", 1)[-1]))
            if target is None:
                unresolved.setdefault(argument, []).append(value)
            else:
                references.append(target)
        for argument, values in unresolved.items():
            attrs[argument] = values if argument.endswith("_ids") else values[0]
        out.append(
            Resource(d.resource.type, d.resource.name, attrs, tuple(dict.fromkeys(references)))
        )
    return tuple(out)
