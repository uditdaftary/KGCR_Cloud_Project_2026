"""Local offline fake AWS adapter for testing and credential-free CLI runs (FD-08).

Provides reproducible simulated harvest snapshots and dry-run apply diffs.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from kgcr.auth.context import SecurityContext
from kgcr.auth.policy import AccessPolicy
from kgcr.aws_adapter.interface import ApplyResult, AWSAdapter, HarvestResult

__all__ = ["LocalFakeAWSAdapter"]


class LocalFakeAWSAdapter(AWSAdapter):
    """Local, offline, fake AWS adapter requiring no AWS credentials or network access."""

    def __init__(self, seeded_resources: list[dict[str, Any]] | None = None) -> None:
        self.seeded_resources = seeded_resources or [
            {
                "type": "aws_s3_bucket",
                "name": "payments_cardholder_backup",
                "properties": {
                    "bucket_name": "payments-cardholder-backup-dev",
                    "server_side_encryption": True,
                },
            },
            {
                "type": "aws_rds_cluster",
                "name": "payments_primary",
                "properties": {
                    "engine": "aurora-postgresql",
                    "multi_az": True,
                    "storage_encrypted": True,
                },
            },
        ]

    def harvest_estate(
        self, account_id: str, ctx: SecurityContext, role_name: str = "KGCRHarvestReadOnly"
    ) -> HarvestResult:
        # Enforce INV-5 read check
        AccessPolicy.enforce_inv5_read(ctx, "harvest_estate")

        return HarvestResult(
            account_id=account_id,
            resources=list(self.seeded_resources),
            read_only_verified=True,
            raw_config_snapshot={
                "account_id": account_id,
                "role_assumed": role_name,
                "external_id_verified": True,
            },
        )

    def generate_plan(self, spec: dict[str, Any], ctx: SecurityContext) -> dict[str, Any]:
        plan_id = f"plan-{uuid4().hex[:8]}"
        resources_to_create = list(spec.keys()) if isinstance(spec, dict) else ["resource-01"]
        return {
            "plan_id": plan_id,
            "spec": spec,
            "actions": {
                "create": resources_to_create,
                "modify": [],
                "destroy": [],
            },
        }

    def apply_plan(
        self,
        plan_id: str,
        spec: dict[str, Any],
        ctx: SecurityContext,
        role_name: str = "KGCRProvisionApply",
    ) -> ApplyResult:
        # Enforce INV-5 write check (only Agent 1 Provisioner role allowed)
        AccessPolicy.enforce_inv5_write(ctx, "apply_plan")

        return ApplyResult(
            plan_id=plan_id,
            applied=True,
            resources_created=list(spec.keys()) if isinstance(spec, dict) else ["resource-01"],
            resources_modified=[],
            resources_destroyed=[],
            errors=[],
        )
