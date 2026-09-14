"""Abstract interface for AWS cloud adapters (FD-08 §3, §4).

Decouples backend orchestration from AWS SDK (boto3) and local test environments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kgcr.auth.context import SecurityContext

__all__ = ["AWSAdapter", "ApplyResult", "HarvestResult"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class HarvestResult:
    """Captured estate configuration snapshot from target AWS account (FD-01 S1b)."""

    account_id: str
    resources: list[dict[str, Any]]
    read_only_verified: bool = True
    harvested_at: str = field(default_factory=_utc_now_iso)
    raw_config_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "resource_count": len(self.resources),
            "read_only_verified": self.read_only_verified,
            "harvested_at": self.harvested_at,
        }


@dataclass(frozen=True)
class ApplyResult:
    """Result of provision plan/apply execution (FD-01 S9, S10)."""

    plan_id: str
    applied: bool
    resources_created: list[str] = field(default_factory=list)
    resources_modified: list[str] = field(default_factory=list)
    resources_destroyed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    executed_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "applied": self.applied,
            "resources_created": len(self.resources_created),
            "resources_modified": len(self.resources_modified),
            "resources_destroyed": len(self.resources_destroyed),
            "errors": self.errors,
            "executed_at": self.executed_at,
        }


class AWSAdapter(ABC):
    """Abstract base adapter for AWS operations."""

    @abstractmethod
    def harvest_estate(
        self, account_id: str, ctx: SecurityContext, role_name: str = "KGCRHarvestReadOnly"
    ) -> HarvestResult:
        """Harvest estate state using Agent 2 read-only role (FD-01 S1b, FD-08 §4.1)."""

    @abstractmethod
    def generate_plan(self, spec: dict[str, Any], ctx: SecurityContext) -> dict[str, Any]:
        """Generate a dry-run provision diff plan (FD-01 S9)."""

    @abstractmethod
    def apply_plan(
        self,
        plan_id: str,
        spec: dict[str, Any],
        ctx: SecurityContext,
        role_name: str = "KGCRProvisionApply",
    ) -> ApplyResult:
        """Apply provision plan using Agent 1 provisioner role (FD-01 S10, FD-08 §4.1)."""
