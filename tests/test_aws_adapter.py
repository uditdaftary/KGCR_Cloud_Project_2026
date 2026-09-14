"""Tests for kgcr.aws_adapter (FD-08 §3, §4)."""

from __future__ import annotations

import pytest

from kgcr.auth.context import ActorRole, SecurityContext
from kgcr.aws_adapter import LocalFakeAWSAdapter
from kgcr.aws_adapter.boto_adapter import Boto3AWSAdapter


def test_fake_aws_adapter_harvest() -> None:
    adapter = LocalFakeAWSAdapter()
    ctx = SecurityContext(user_ref="harvester_user", role=ActorRole.AGENT2_HARVESTER)

    res = adapter.harvest_estate(account_id="123456789012", ctx=ctx)
    assert res.account_id == "123456789012"
    assert res.read_only_verified is True
    assert len(res.resources) >= 2
    assert res.resources[0]["type"] == "aws_s3_bucket"


def test_fake_aws_adapter_plan_and_apply() -> None:
    adapter = LocalFakeAWSAdapter()
    prov_ctx = SecurityContext(user_ref="provisioner_user", role=ActorRole.AGENT1_PROVISIONER)

    spec = {"aws_s3_bucket.payments": {"bucket_name": "payments-cardholder"}}
    plan = adapter.generate_plan(spec, ctx=prov_ctx)
    assert "plan_id" in plan
    assert "actions" in plan

    result = adapter.apply_plan(plan["plan_id"], spec, ctx=prov_ctx)
    assert result.applied is True
    assert "aws_s3_bucket.payments" in result.resources_created


def test_aws_adapter_inv5_enforcement() -> None:
    adapter = LocalFakeAWSAdapter()
    harvester_ctx = SecurityContext(user_ref="harvester", role=ActorRole.AGENT2_HARVESTER)

    # Harvester cannot apply plan (INV-5 write boundary)
    with pytest.raises(PermissionError, match="INV-5 Violation"):
        adapter.apply_plan("plan-123", {"res": "val"}, ctx=harvester_ctx)


def test_boto3_adapter_offline_fallback() -> None:
    adapter = Boto3AWSAdapter(external_id="ext-12345")
    ctx = SecurityContext(user_ref="harvester", role=ActorRole.AGENT2_HARVESTER)

    res = adapter.harvest_estate("999888777666", ctx=ctx)
    assert res.account_id == "999888777666"
    assert res.read_only_verified is True
    assert len(res.resources) >= 1
