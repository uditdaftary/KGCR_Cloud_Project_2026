"""Tests for kgcr.service (FD-01, FD-03)."""

from __future__ import annotations

from kgcr.auth import ActorRole, SecurityContext
from kgcr.aws_adapter import LocalFakeAWSAdapter
from kgcr.persistence import SQLiteRunStore
from kgcr.service import KGCRBackendService


def test_service_execute_design_lifecycle() -> None:
    store = SQLiteRunStore(":memory:")
    service = KGCRBackendService(repository=store, aws_adapter=LocalFakeAWSAdapter())
    ctx = SecurityContext(user_ref="manya", role=ActorRole.ARCHITECT, account_id="111222333444")

    res = service.execute_design(
        intent_statement="payments API with PCI-DSS",
        ctx=ctx,
        audience="architect",
        plan_only=True,
    )

    assert res.terminal_state == "PLAN_ONLY"
    assert res.spec_hash is not None
    assert res.run_id is not None

    # Check persistence
    stored_run = store.get_run(res.run_id)
    assert stored_run is not None
    assert stored_run.mode == "design"
    assert stored_run.audience == "architect"
    assert stored_run.account_id == "111222333444"

    # Check explanation persistence
    expl = store.get_explanation(res.run_id)
    assert expl is not None
    assert expl.audience == "architect"
    assert "justification_subgraph" in expl.content


def test_service_execute_review_lifecycle() -> None:
    store = SQLiteRunStore(":memory:")
    service = KGCRBackendService(repository=store, aws_adapter=LocalFakeAWSAdapter())
    ctx = SecurityContext(user_ref="auditor_user", role=ActorRole.AGENT2_HARVESTER)

    res = service.execute_review(
        account_id="555666777888", ctx=ctx, audience="auditor", attest_only=True
    )

    assert res.terminal_state == "ATTESTED"
    assert res.run_id is not None

    stored_run = store.get_run(res.run_id)
    assert stored_run is not None
    assert stored_run.mode == "review"
    assert stored_run.account_id == "555666777888"


def test_service_query_history() -> None:
    store = SQLiteRunStore(":memory:")
    service = KGCRBackendService(repository=store, aws_adapter=LocalFakeAWSAdapter())

    ctx1 = SecurityContext(user_ref="user1", role=ActorRole.ARCHITECT, account_id="acc-1")
    ctx2 = SecurityContext(user_ref="user2", role=ActorRole.AGENT2_HARVESTER, account_id="acc-2")

    service.execute_design("intent 1", ctx=ctx1)
    service.execute_review("acc-2", ctx=ctx2)

    history_all = service.query_history()
    assert len(history_all) == 2

    history_acc1 = service.query_history(account_id="acc-1")
    assert len(history_acc1) == 1
    assert history_acc1[0].account_id == "acc-1"

    history_review = service.query_history(mode="review")
    assert len(history_review) == 1
    assert history_review[0].mode == "review"
