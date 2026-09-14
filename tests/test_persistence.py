"""Tests for kgcr.persistence (FD-03, FD-06)."""

from __future__ import annotations

from pathlib import Path

from kgcr.persistence import (
    SQLiteRunStore,
    StoredExplanation,
    StoredRun,
    StoredSpec,
    StoredWaiver,
)
from kgcr.runrecord import RunRecord


def test_sqlite_store_run_lifecycle() -> None:
    store = SQLiteRunStore(":memory:")
    rr = RunRecord(
        spec_hash="abc123hash",
        graph_version="p1-v1.0",
        model_version="p8-v1.0",
        seed=42,
    )
    stored_run = StoredRun(
        run_record=rr,
        mode="design",
        audience="architect",
        terminal_state="DEPLOYED",
        account_id="123456789012",
        payload={"notes": "test run"},
    )

    run_id = store.save_run(stored_run)
    assert run_id == stored_run.run_id

    retrieved = store.get_run(run_id)
    assert retrieved is not None
    assert retrieved.run_id == stored_run.run_id
    assert retrieved.spec_hash == "abc123hash"
    assert retrieved.mode == "design"
    assert retrieved.audience == "architect"
    assert retrieved.account_id == "123456789012"
    assert retrieved.payload == {"notes": "test run"}

    store.close()


def test_sqlite_store_list_runs_filtering() -> None:
    store = SQLiteRunStore(":memory:")

    run1 = StoredRun(
        run_record=RunRecord(spec_hash="hash1", graph_version="v1", model_version="v1", seed=1),
        mode="design",
        terminal_state="DEPLOYED",
        account_id="acc-prod",
    )
    run2 = StoredRun(
        run_record=RunRecord(spec_hash="hash2", graph_version="v1", model_version="v1", seed=2),
        mode="review",
        terminal_state="ATTESTED",
        account_id="acc-dev",
    )

    store.save_run(run1)
    store.save_run(run2)

    all_runs = store.list_runs()
    assert len(all_runs) == 2

    prod_runs = store.list_runs(account_id="acc-prod")
    assert len(prod_runs) == 1
    assert prod_runs[0].account_id == "acc-prod"

    review_runs = store.list_runs(mode="review")
    assert len(review_runs) == 1
    assert review_runs[0].mode == "review"

    store.close()


def test_sqlite_store_spec_lifecycle() -> None:
    store = SQLiteRunStore(":memory:")
    spec = StoredSpec(
        spec_id="spec-001",
        spec_hash="hash-spec-001",
        content={"compute": {"instance_type": "m6i.xlarge"}},
    )

    saved_id = store.save_spec(spec)
    assert saved_id == "spec-001"

    by_id = store.get_spec("spec-001")
    assert by_id is not None
    assert by_id.spec_hash == "hash-spec-001"
    assert by_id.content["compute"]["instance_type"] == "m6i.xlarge"

    by_hash = store.get_spec("hash-spec-001")
    assert by_hash is not None
    assert by_hash.spec_id == "spec-001"

    store.close()


def test_sqlite_store_explanation_lifecycle() -> None:
    store = SQLiteRunStore(":memory:")
    rr = RunRecord(spec_hash="hash_expl", graph_version="v1", model_version="v1", seed=42)
    run = StoredRun(run_record=rr)
    store.save_run(run)

    explanation = StoredExplanation(
        bundle_id="b-001",
        run_id=run.run_id,
        audience="auditor",
        content={"justification_subgraph": ["node1", "node2"]},
    )

    saved_b_id = store.save_explanation(explanation)
    assert saved_b_id == "b-001"

    retrieved = store.get_explanation(run.run_id, audience="auditor")
    assert retrieved is not None
    assert retrieved.bundle_id == "b-001"
    assert retrieved.audience == "auditor"
    assert retrieved.content == {"justification_subgraph": ["node1", "node2"]}

    store.close()


def test_sqlite_store_waiver_lifecycle() -> None:
    store = SQLiteRunStore(":memory:")
    rr = RunRecord(spec_hash="hash_waiver", graph_version="v1", model_version="v1", seed=42)
    run = StoredRun(run_record=rr)
    store.save_run(run)

    waiver = StoredWaiver(
        waiver_id="w-001",
        finding_id="F-003",
        run_id=run.run_id,
        user_ref="manya-student2",
        justification="Accepted risk for dev environment",
    )

    saved_w_id = store.save_waiver(waiver)
    assert saved_w_id == "w-001"

    waivers = store.list_waivers(run_id=run.run_id)
    assert len(waivers) == 1
    assert waivers[0].waiver_id == "w-001"
    assert waivers[0].finding_id == "F-003"
    assert waivers[0].justification == "Accepted risk for dev environment"

    store.close()


def test_sqlite_store_file_persistence(tmp_path: Path) -> None:
    db_file = tmp_path / "test_kgcr.db"
    store1 = SQLiteRunStore(db_file)

    rr = RunRecord(spec_hash="file_hash", graph_version="v1", model_version="v1", seed=10)
    run = StoredRun(run_record=rr, account_id="acc-persisted")
    store1.save_run(run)
    store1.close()

    # Re-open database from file
    store2 = SQLiteRunStore(db_file)
    retrieved = store2.get_run(run.run_id)
    assert retrieved is not None
    assert retrieved.account_id == "acc-persisted"
    store2.close()
