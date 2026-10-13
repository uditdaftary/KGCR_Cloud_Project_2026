"""The AWS Config harvest, against canned items and against moto. No real AWS is called.

The canned responses go through botocore's ``Stubber`` on a real ``config`` client, so their
shape is checked against the service model; the field names inside ``configuration`` come from
the AWS Config resource schema.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

pytest.importorskip("boto3")

import boto3  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

from kgcr.defects.detectors import resource_findings  # noqa: E402
from kgcr.harvest.config import SUPPORTED_TYPES, harvest_account  # noqa: E402

REGION = "eu-west-1"
ACCOUNT = "123456789012"
KEY_ARN = f"arn:aws:kms:{REGION}:{ACCOUNT}:key/key-1"


def _client() -> Any:
    return boto3.client(
        "config",
        region_name=REGION,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


def _item(rtype: str, rid: str, name: str | None, cfg: Any, supp: Any = None, **extra: Any) -> Any:
    item: dict[str, Any] = {
        "accountId": ACCOUNT,
        "awsRegion": REGION,
        "resourceType": rtype,
        "resourceId": rid,
        "configurationItemStatus": "OK",
        "configuration": json.dumps(cfg) if cfg is not None else "",
        "supplementaryConfiguration": {k: json.dumps(v) for k, v in (supp or {}).items()},
        **extra,
    }
    if name:
        item["resourceName"] = name
    return item


def _ids(rtype: str, *ids: str) -> dict[str, Any]:
    return {"resourceIdentifiers": [{"resourceType": rtype, "resourceId": i} for i in ids]}


def _stub_account(stub: Stubber) -> None:
    """One database, one bucket, two security groups over two pages, an instance, two keys."""
    rds, s3, sg, ec2, kms = SUPPORTED_TYPES

    stub.add_response("list_discovered_resources", _ids(rds, "cardholder-db", "old-db"))
    stub.add_response(
        "batch_get_resource_config",
        {
            "baseConfigurationItems": [
                _item(
                    rds,
                    "cardholder-db",
                    "cardholder-db",
                    {
                        "dBInstanceIdentifier": "cardholder-db",
                        "engine": "postgres",
                        "storageEncrypted": False,
                        "publiclyAccessible": False,
                        "vpcSecurityGroups": [{"vpcSecurityGroupId": "sg-app", "status": "active"}],
                        "kmsKeyId": KEY_ARN,
                    },
                ),
                _item(rds, "old-db", None, None, configurationItemStatus="ResourceDeleted"),
            ]
        },
        {
            "resourceKeys": [
                {"resourceType": rds, "resourceId": i} for i in ("cardholder-db", "old-db")
            ]
        },
    )

    stub.add_response("list_discovered_resources", _ids(s3, "kgcr-logs"))
    stub.add_response(
        "batch_get_resource_config",
        {
            "baseConfigurationItems": [
                _item(
                    s3,
                    "kgcr-logs",
                    "kgcr-logs",
                    {"name": "kgcr-logs"},
                    {
                        "PublicAccessBlockConfiguration": {
                            "blockPublicAcls": True,
                            "blockPublicPolicy": True,
                            "ignorePublicAcls": True,
                            "restrictPublicBuckets": True,
                        },
                        "ServerSideEncryptionConfiguration": {
                            "rules": [
                                {"applyServerSideEncryptionByDefault": {"sseAlgorithm": "AES256"}}
                            ]
                        },
                    },
                )
            ]
        },
    )

    page_one = _ids(sg, "sg-app")
    page_one["nextToken"] = "page-2"
    stub.add_response("list_discovered_resources", page_one, {"resourceType": sg})
    stub.add_response(
        "list_discovered_resources",
        _ids(sg, "sg-extra"),
        {"resourceType": sg, "nextToken": "page-2"},
    )
    ssh_open = {
        "fromPort": 22,
        "toPort": 22,
        "ipProtocol": "tcp",
        "ipv4Ranges": [{"cidrIp": "0.0.0.0/0"}],
        "ipRanges": ["0.0.0.0/0"],
    }
    stub.add_response(
        "batch_get_resource_config",
        {
            "baseConfigurationItems": [
                _item(
                    sg,
                    "sg-app",
                    "app",
                    {
                        "groupId": "sg-app",
                        "groupName": "app",
                        "vpcId": "vpc-1",
                        "ipPermissions": [ssh_open],
                        "ipPermissionsEgress": [
                            {"ipProtocol": "-1", "ipv4Ranges": [{"cidrIp": "0.0.0.0/0"}]}
                        ],
                    },
                )
            ],
            "unprocessedResourceKeys": [{"resourceType": sg, "resourceId": "sg-extra"}],
        },
    )

    stub.add_response("list_discovered_resources", _ids(ec2, "i-1"))
    stub.add_response(
        "batch_get_resource_config",
        {
            "baseConfigurationItems": [
                _item(
                    ec2,
                    "i-1",
                    None,
                    {
                        "instanceId": "i-1",
                        "imageId": "ami-1",
                        "instanceType": "t3.micro",
                        "publicIpAddress": "203.0.113.7",
                        "securityGroups": [{"groupId": "sg-app", "groupName": "app"}],
                        "metadataOptions": {"httpTokens": "optional", "httpEndpoint": "enabled"},
                    },
                )
            ]
        },
    )

    stub.add_response("list_discovered_resources", _ids(kms, "key-1", "aws-key"))
    stub.add_response(
        "batch_get_resource_config",
        {
            "baseConfigurationItems": [
                _item(
                    kms,
                    "key-1",
                    None,
                    {"keyId": "key-1", "enabled": True, "keyManager": "CUSTOMER"},
                ),
                _item(kms, "aws-key", None, {"keyId": "aws-key", "keyManager": "AWS"}),
            ]
        },
    )


@pytest.fixture(scope="module")
def harvest():  # type: ignore[no-untyped-def]
    client = _client()
    with Stubber(client) as stub:
        _stub_account(stub)
        result = harvest_account(client, region=REGION)
        stub.assert_no_pending_responses()
    return result


def test_each_supported_type_becomes_provider_shaped_resources(harvest) -> None:  # type: ignore[no-untyped-def]
    by_address = {r.address: r for r in harvest.resources}
    assert set(by_address) == {
        "aws_db_instance.cardholder-db",
        "aws_s3_bucket.kgcr-logs",
        "aws_s3_bucket_public_access_block.kgcr-logs",
        "aws_s3_bucket_server_side_encryption_configuration.kgcr-logs",
        "aws_security_group.app",
        "aws_instance.i-1",
        "aws_kms_key.key-1",
    }
    assert harvest.account_id == ACCOUNT and harvest.region == REGION
    sse = by_address["aws_s3_bucket_server_side_encryption_configuration.kgcr-logs"]
    assert sse.attributes["rule"][0]["apply_server_side_encryption_by_default"] == {
        "sse_algorithm": "AES256"
    }
    assert by_address["aws_instance.i-1"].attributes["associate_public_ip_address"] is True


def test_ids_that_name_harvested_resources_become_references(harvest) -> None:  # type: ignore[no-untyped-def]
    by_address = {r.address: r for r in harvest.resources}
    db = by_address["aws_db_instance.cardholder-db"]
    assert set(db.references) == {"aws_security_group.app", "aws_kms_key.key-1"}
    assert "kms_key_id" not in db.attributes and "vpc_security_group_ids" not in db.attributes
    assert by_address["aws_instance.i-1"].references == ("aws_security_group.app",)


def test_the_rule_floor_reads_a_harvested_estate(harvest) -> None:  # type: ignore[no-untyped-def]
    by_address = {r.address: r for r in harvest.resources}
    assert {f.rule_id for f in resource_findings(by_address["aws_db_instance.cardholder-db"])} == {
        "CKV_AWS_16"
    }
    assert {f.rule_id for f in resource_findings(by_address["aws_security_group.app"])} == {
        "CKV_AWS_260"
    }
    assert resource_findings(by_address["aws_s3_bucket.kgcr-logs"]) == []


def test_everything_not_read_is_listed_not_dropped(harvest) -> None:  # type: ignore[no-untyped-def]
    reasons = {(s.resource_id, s.reason) for s in harvest.skipped}
    assert ("old-db", "no readable configuration: ResourceDeleted") in reasons
    assert ("sg-extra", "not processed by Config") in reasons
    assert ("aws-key", "AWS-managed key") in reasons
    assert any("tags" in c for c in harvest.caveats)


def test_the_harvest_only_reads() -> None:
    class Recorder:
        calls: list[str] = []

        def list_discovered_resources(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append("list_discovered_resources")
            return {}

        def batch_get_resource_config(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append("batch_get_resource_config")
            return {}

    recorder = Recorder()
    empty = harvest_account(recorder, region=REGION)
    assert empty.resources == () and set(recorder.calls) == {"list_discovered_resources"}


def test_a_hundred_and_one_resources_take_two_batches() -> None:
    class Many:
        batches: list[int] = []

        def list_discovered_resources(self, **kwargs: Any) -> dict[str, Any]:
            if kwargs["resourceType"] != "AWS::KMS::Key":
                return {}
            return _ids("AWS::KMS::Key", *(f"k{i}" for i in range(101)))

        def batch_get_resource_config(self, **kwargs: Any) -> dict[str, Any]:
            keys = kwargs["resourceKeys"]
            self.batches.append(len(keys))
            return {
                "baseConfigurationItems": [
                    _item(k["resourceType"], k["resourceId"], None, {"keyId": k["resourceId"]})
                    for k in keys
                ]
            }

    many = Many()
    result = harvest_account(many, region=REGION)
    assert many.batches == [100, 1] and len(result.resources) == 101


def test_against_moto_an_s3_bucket_comes_back_through_the_real_client() -> None:
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(
            Bucket="kgcr-demo", CreateBucketConfiguration={"LocationConstraint": REGION}
        )
        config = boto3.client("config", region_name=REGION)
        config.put_configuration_recorder(
            ConfigurationRecorder={
                "name": "default",
                "roleARN": f"arn:aws:iam::{ACCOUNT}:role/config",
                "recordingGroup": {"allSupported": True},
            }
        )
        config.put_delivery_channel(
            DeliveryChannel={"name": "default", "s3BucketName": "kgcr-demo"}
        )
        config.start_configuration_recorder(ConfigurationRecorderName="default")
        result = harvest_account(config, region=REGION)
    assert [r.address for r in result.resources] == ["aws_s3_bucket.kgcr-demo"]
    assert result.resources[0].attributes == {"bucket": "kgcr-demo"}
