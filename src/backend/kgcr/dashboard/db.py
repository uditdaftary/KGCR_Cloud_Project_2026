"""The dashboard's local SQLite store: catalog numbers, sessions, jobs.

One connection per call (the server is threaded) in WAL mode. Every artifact the
dashboard creates takes the next catalog number; numbers 000 to 099 are reserved
for the fixed views, so the sequence starts at 100.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["Database", "now_iso"]

FIRST_CATALOG_NO = 100

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog (
    no INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    catalog_no INTEGER NOT NULL REFERENCES catalog(no),
    role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
    started_at TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_no INTEGER NOT NULL REFERENCES catalog(no),
    session_id TEXT REFERENCES sessions(id),
    kind TEXT NOT NULL,
    params TEXT NOT NULL,
    live INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled')),
    exit_code INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    log TEXT NOT NULL DEFAULT '',
    output_dir TEXT,
    run_prefix TEXT,
    live_calls INTEGER
);
CREATE INDEX IF NOT EXISTS jobs_session ON jobs(session_id);
-- Human decisions only, append-only: the code has no UPDATE or DELETE for this table.
CREATE TABLE IF NOT EXISTS control_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    control_node TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('verified', 'needs_change', 'rejected')),
    proposed_summary TEXT,
    note TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gold_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    framework TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    config_json TEXT NOT NULL,
    controls_json TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'authored', 'reviewed')),
    reviewer TEXT,
    review_note TEXT,
    review_check_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(_SCHEMA)
            # Idempotent: seeds the AUTOINCREMENT counter only on a fresh database.
            if c.execute("SELECT 1 FROM sqlite_sequence WHERE name = 'catalog'").fetchone() is None:
                c.execute(
                    "INSERT INTO sqlite_sequence (name, seq) VALUES ('catalog', ?)",
                    (FIRST_CATALOG_NO - 1,),
                )
            # A job cannot survive the server that ran it.
            c.execute(
                "UPDATE jobs SET status = 'failed', finished_at = ?, "
                "log = log || '\n[dashboard] server stopped before this job finished\n' "
                "WHERE status IN ('queued', 'running')",
                (now_iso(),),
            )

    def connection(self) -> AbstractContextManager[sqlite3.Connection]:
        """A short-lived connection for the stores that share this file (authoring)."""
        return self._conn()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _next_no(c: sqlite3.Connection, kind: str) -> int:
        cur = c.execute("INSERT INTO catalog (kind, created_at) VALUES (?, ?)", (kind, now_iso()))
        assert cur.lastrowid is not None
        return cur.lastrowid

    # --- sessions ----------------------------------------------------------------

    def create_session(self, role: str) -> dict[str, Any]:
        sid, ts = uuid.uuid4().hex, now_iso()
        with self._conn() as c:
            no = self._next_no(c, "session")
            c.execute(
                "INSERT INTO sessions (id, catalog_no, role, started_at, last_seen) "
                "VALUES (?, ?, ?, ?, ?)",
                (sid, no, role, ts, ts),
            )
        return {"id": sid, "catalog_no": no, "role": role, "started_at": ts}

    def session(self, sid: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
            if row is not None:
                c.execute("UPDATE sessions SET last_seen = ? WHERE id = ?", (now_iso(), sid))
        return dict(row) if row else None

    def sessions(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT s.*, COUNT(j.id) AS jobs, "
                "SUM(j.kind = 'review' AND j.status = 'done') AS reviews "
                "FROM sessions s LEFT JOIN jobs j ON j.session_id = s.id "
                "GROUP BY s.id ORDER BY s.catalog_no DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # --- jobs ----------------------------------------------------------------------

    def create_job(self, session_id: str, kind: str, params: dict[str, Any], live: bool) -> int:
        with self._conn() as c:
            no = self._next_no(c, f"job:{kind}")
            cur = c.execute(
                "INSERT INTO jobs (catalog_no, session_id, kind, params, live, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'queued', ?)",
                (no, session_id, kind, json.dumps(params, sort_keys=True), int(live), now_iso()),
            )
            assert cur.lastrowid is not None
            return cur.lastrowid

    def update_job(self, job_id: int, **fields: Any) -> None:
        allowed = {
            "status", "exit_code", "started_at", "finished_at", "log",
            "output_dir", "run_prefix", "live_calls",
        }  # fmt: skip
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"not a job column: {sorted(unknown)}")
        cols = ", ".join(f"{k} = ?" for k in fields)  # keys checked against the allow-list
        with self._conn() as c:
            c.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*fields.values(), job_id))

    def job(self, job_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _job_row(row) if row else None

    def jobs(self, session_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Newest first, without the log (up to 200 KB a row; ``job()`` has it)."""
        sql, args = f"SELECT {_LISTED_COLUMNS} FROM jobs", []
        if session_id is not None:
            sql, args = sql + " WHERE session_id = ?", [session_id]
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [_job_row(r) for r in rows]

    def jobs_with_runs(self) -> list[dict[str, Any]]:
        """Every job that stored a run, so run history can link back to its catalog entry."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, catalog_no, session_id, run_prefix FROM jobs "
                "WHERE run_prefix IS NOT NULL ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


_LISTED_COLUMNS = (
    "id, catalog_no, session_id, kind, params, live, status, exit_code, created_at, "
    "started_at, finished_at, output_dir, run_prefix, live_calls"
)


def _job_row(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    out["params"] = json.loads(out["params"])
    out["live"] = bool(out["live"])
    return out
