"""SQLite implementation of the RunRepository interface (FD-03, FD-06).

Provides an offline, zero-dependency file-based or in-memory persistence store.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kgcr.persistence.repository import RunRepository
from kgcr.persistence.schema import (
    INIT_DB_SQL,
    StoredExplanation,
    StoredRun,
    StoredSpec,
    StoredWaiver,
)

__all__ = ["SQLiteRunStore"]


class SQLiteRunStore(RunRepository):
    """SQLite-backed persistence store for run records, specs, explanations, and waivers."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        # Use check_same_thread=False for flexibility if used in multithreaded test runners
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.executescript(INIT_DB_SQL)

    def close(self) -> None:
        self._conn.close()

    def save_run(self, run: StoredRun) -> str:
        payload_json = json.dumps(run.to_dict(), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO runs (
                    run_id, spec_hash, graph_version, model_version, seed,
                    mode, audience, terminal_state, account_id, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    mode=excluded.mode,
                    audience=excluded.audience,
                    terminal_state=excluded.terminal_state,
                    account_id=excluded.account_id,
                    payload_json=excluded.payload_json;
                """,
                (
                    run.run_id,
                    run.spec_hash,
                    run.run_record.graph_version,
                    run.run_record.model_version,
                    run.run_record.seed,
                    run.mode,
                    run.audience,
                    run.terminal_state,
                    run.account_id,
                    run.created_at,
                    payload_json,
                ),
            )
        return run.run_id

    def get_run(self, run_id: str) -> StoredRun | None:
        cursor = self._conn.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        data: dict[str, Any] = json.loads(row["payload_json"])
        return StoredRun.from_dict(data)

    def list_runs(
        self,
        *,
        account_id: str | None = None,
        mode: str | None = None,
        terminal_state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StoredRun]:
        query = "SELECT payload_json FROM runs WHERE 1=1"
        params: list[Any] = []

        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)
        if mode is not None:
            query += " AND mode = ?"
            params.append(mode)
        if terminal_state is not None:
            query += " AND terminal_state = ?"
            params.append(terminal_state)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()
        return [StoredRun.from_dict(json.loads(row["payload_json"])) for row in rows]

    def save_spec(self, spec: StoredSpec) -> str:
        content_json = json.dumps(spec.content, sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO specifications (spec_id, spec_hash, content_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(spec_id) DO UPDATE SET
                    content_json=excluded.content_json;
                """,
                (spec.spec_id, spec.spec_hash, content_json, spec.created_at),
            )
        return spec.spec_id

    def get_spec(self, spec_id_or_hash: str) -> StoredSpec | None:
        cursor = self._conn.execute(
            """
            SELECT spec_id, spec_hash, content_json, created_at
            FROM specifications
            WHERE spec_id = ? OR spec_hash = ?
            """,
            (spec_id_or_hash, spec_id_or_hash),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return StoredSpec(
            spec_id=row["spec_id"],
            spec_hash=row["spec_hash"],
            content=json.loads(row["content_json"]),
            created_at=row["created_at"],
        )

    def save_explanation(self, explanation: StoredExplanation) -> str:
        content_json = json.dumps(explanation.content, sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO explanations (bundle_id, run_id, audience, content_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(bundle_id) DO UPDATE SET
                    content_json=excluded.content_json;
                """,
                (
                    explanation.bundle_id,
                    explanation.run_id,
                    explanation.audience,
                    content_json,
                    explanation.created_at,
                ),
            )
        return explanation.bundle_id

    def get_explanation(self, run_id: str, audience: str | None = None) -> StoredExplanation | None:
        query = (
            "SELECT bundle_id, run_id, audience, content_json, created_at "
            "FROM explanations WHERE run_id = ?"
        )
        params: list[Any] = [run_id]

        if audience is not None:
            query += " AND audience = ?"
            params.append(audience)

        query += " ORDER BY created_at DESC LIMIT 1"
        cursor = self._conn.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            return None

        return StoredExplanation(
            bundle_id=row["bundle_id"],
            run_id=row["run_id"],
            audience=row["audience"],
            content=json.loads(row["content_json"]),
            created_at=row["created_at"],
        )

    def save_waiver(self, waiver: StoredWaiver) -> str:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO waivers (
                    waiver_id, finding_id, run_id, user_ref, justification, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(waiver_id) DO UPDATE SET
                    justification=excluded.justification,
                    expires_at=excluded.expires_at;
                """,
                (
                    waiver.waiver_id,
                    waiver.finding_id,
                    waiver.run_id,
                    waiver.user_ref,
                    waiver.justification,
                    waiver.expires_at,
                    waiver.created_at,
                ),
            )
        return waiver.waiver_id

    def list_waivers(
        self, *, run_id: str | None = None, finding_id: str | None = None
    ) -> Sequence[StoredWaiver]:
        query = (
            "SELECT waiver_id, finding_id, run_id, user_ref, justification, expires_at, "
            "created_at FROM waivers WHERE 1=1"
        )
        params: list[Any] = []

        if run_id is not None:
            query += " AND run_id = ?"
            params.append(run_id)
        if finding_id is not None:
            query += " AND finding_id = ?"
            params.append(finding_id)

        query += " ORDER BY created_at DESC"
        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()
        return [
            StoredWaiver(
                waiver_id=row["waiver_id"],
                finding_id=row["finding_id"],
                run_id=row["run_id"],
                user_ref=row["user_ref"],
                justification=row["justification"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
