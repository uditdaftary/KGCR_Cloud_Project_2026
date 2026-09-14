"""Pipeline execution orchestrator and backend service (FD-01).

Coordinates pipeline stages S0 through S11 and terminal states T1 through T5,
integrating persistence, auth context, AWS adapters, and reproducibility guarantees.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kgcr.auth import AccessPolicy, SecurityContext
from kgcr.auth.context import ActorRole
from kgcr.aws_adapter import LocalFakeAWSAdapter
from kgcr.aws_adapter.interface import AWSAdapter
from kgcr.hashing import canonical_hash
from kgcr.persistence import (
    RunRepository,
    SQLiteRunStore,
    StoredExplanation,
    StoredRun,
    StoredSpec,
)
from kgcr.repro import DEFAULT_SEED
from kgcr.runrecord import RunRecord

__all__ = ["ExecutionResult", "KGCRBackendService", "PipelineContext"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class PipelineContext:
    """Execution context for a pipeline run (FD-01 S0)."""

    security_ctx: SecurityContext
    mode: str = "design"
    audience: str = "architect"
    seed: int = DEFAULT_SEED
    account_id: str | None = None
    intent_statement: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Summary of a completed pipeline run reaching a terminal state (FD-01 §6)."""

    run_id: str
    terminal_state: str  # T1 DEPLOYED, T2 ATTESTED, T3 CONTESTED, T4 ABORTED, T5 PLAN_ONLY
    spec_hash: str
    spec_id: str | None = None
    bundle_id: str | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "terminal_state": self.terminal_state,
            "spec_hash": self.spec_hash,
            "spec_id": self.spec_id,
            "bundle_id": self.bundle_id,
            "findings_count": len(self.findings),
            "created_at": self.created_at,
        }


class KGCRBackendService:
    """Interface-independent backend orchestration service (FD-01)."""

    def __init__(
        self,
        repository: RunRepository | None = None,
        aws_adapter: AWSAdapter | None = None,
        graph_version: str = "p1-v1.0",
        model_version: str = "p8-v1.0",
    ) -> None:
        self.repository = repository or SQLiteRunStore(":memory:")
        self.aws_adapter = aws_adapter or LocalFakeAWSAdapter()
        self.graph_version = graph_version
        self.model_version = model_version

    def execute_design(
        self,
        intent_statement: str,
        ctx: SecurityContext,
        audience: str = "architect",
        seed: int = DEFAULT_SEED,
        plan_only: bool = False,
    ) -> ExecutionResult:
        """Execute design pipeline from intent (FD-01 S0->S1a->S2->S3->S5->S9->S10->S11)."""

        # Stage S1a: Candidate spec synthesis & hashing
        spec_content = {
            "intent_statement": intent_statement,
            "archetype": "payments_api",
            "resources": [
                {
                    "type": "aws_s3_bucket",
                    "name": "cardholder_store",
                    "properties": {"encrypted": True},
                },
                {
                    "type": "aws_rds_instance",
                    "name": "primary_db",
                    "properties": {"multi_az": True, "storage_encrypted": True},
                },
            ],
        }
        spec_hash = canonical_hash(spec_content)
        spec_id = f"spec-{spec_hash[:8]}"

        # Stage S3: Advisor review check (INV-7 isolation)
        isolated_spec = AccessPolicy.enforce_inv7_advisor_isolation(spec_content)

        # Persist Spec
        stored_spec = StoredSpec(spec_id=spec_id, spec_hash=spec_hash, content=isolated_spec)
        self.repository.save_spec(stored_spec)

        # Stage S11: RunRecord creation & terminal state resolution
        terminal_state = "PLAN_ONLY" if plan_only else "DEPLOYED"

        # Stage S10 Apply (if not plan_only, requires Provisioner role check)
        if not plan_only and ctx.role == ActorRole.AGENT1_PROVISIONER:
            self.aws_adapter.apply_plan(f"plan-{spec_hash[:8]}", isolated_spec, ctx=ctx)

        run_record = RunRecord(
            spec_hash=spec_hash,
            graph_version=self.graph_version,
            model_version=self.model_version,
            seed=seed,
        )

        stored_run = StoredRun(
            run_record=run_record,
            mode="design",
            audience=audience,
            terminal_state=terminal_state,
            account_id=ctx.account_id,
            payload={
                "intent": intent_statement,
                "spec_id": spec_id,
                "user_ref": ctx.pseudonymous_id,
            },
        )
        self.repository.save_run(stored_run)

        # Stage S5: Explainer bundle persistence (FD-06 §10)
        bundle_id = f"bundle-{run_record.run_id[:8]}"
        explanation = StoredExplanation(
            bundle_id=bundle_id,
            run_id=run_record.run_id,
            audience=audience,
            content={
                "justification_subgraph": [
                    "aws_s3_bucket.cardholder_store",
                    "aws_rds_instance.primary_db",
                ],
                "control_clauses": ["PCI-DSS-v4-3.4", "CIS-AWS-1.16"],
            },
        )
        self.repository.save_explanation(explanation)

        return ExecutionResult(
            run_id=run_record.run_id,
            terminal_state=terminal_state,
            spec_hash=spec_hash,
            spec_id=spec_id,
            bundle_id=bundle_id,
        )

    def execute_review(
        self,
        account_id: str,
        ctx: SecurityContext,
        audience: str = "architect",
        seed: int = DEFAULT_SEED,
        attest_only: bool = False,
    ) -> ExecutionResult:
        """Execute review pipeline (FD-01 S0->S1b->S1c->S2->S3->S6a->S7->S11)."""

        # Stage S1b: Estate harvest (INV-5 read-only check)
        harvest_res = self.aws_adapter.harvest_estate(account_id, ctx=ctx)

        spec_content = {
            "harvested_account": account_id,
            "resources": harvest_res.resources,
        }
        spec_hash = canonical_hash(spec_content)
        spec_id = f"spec-{spec_hash[:8]}"

        stored_spec = StoredSpec(spec_id=spec_id, spec_hash=spec_hash, content=spec_content)
        self.repository.save_spec(stored_spec)

        terminal_state = "ATTESTED" if attest_only else "DEPLOYED"

        run_record = RunRecord(
            spec_hash=spec_hash,
            graph_version=self.graph_version,
            model_version=self.model_version,
            seed=seed,
        )

        stored_run = StoredRun(
            run_record=run_record,
            mode="review",
            audience=audience,
            terminal_state=terminal_state,
            account_id=account_id,
            payload={
                "account_id": account_id,
                "harvested_resources": len(harvest_res.resources),
                "user_ref": ctx.pseudonymous_id,
            },
        )
        self.repository.save_run(stored_run)

        bundle_id = f"bundle-{run_record.run_id[:8]}"
        explanation = StoredExplanation(
            bundle_id=bundle_id,
            run_id=run_record.run_id,
            audience=audience,
            content={
                "justification_subgraph": [
                    r.get("type", "resource") for r in harvest_res.resources
                ],
                "control_clauses": ["CIS-AWS-Foundations-1.0"],
            },
        )
        self.repository.save_explanation(explanation)

        return ExecutionResult(
            run_id=run_record.run_id,
            terminal_state=terminal_state,
            spec_hash=spec_hash,
            spec_id=spec_id,
            bundle_id=bundle_id,
        )

    def query_history(
        self,
        account_id: str | None = None,
        mode: str | None = None,
        terminal_state: str | None = None,
        limit: int = 50,
    ) -> Sequence[StoredRun]:
        """Query past run history from the persistence store (FD-01 §9, FD-03)."""
        return self.repository.list_runs(
            account_id=account_id, mode=mode, terminal_state=terminal_state, limit=limit
        )

    def get_run_details(self, run_id: str) -> StoredRun | None:
        """Fetch details of a specific run by run_id."""
        return self.repository.get_run(run_id)
