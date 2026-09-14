"""Dataclasses and SQL schema for persistence entities (FD-03, FD-06).

Represents stored runs, candidate specifications, explanation bundles, and waivers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kgcr.runrecord import RunRecord

__all__ = [
    "INIT_DB_SQL",
    "StoredExplanation",
    "StoredRun",
    "StoredSpec",
    "StoredWaiver",
]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class StoredRun:
    """Indexed run entry wrapping a RunRecord and metadata (FD-03 §4)."""

    run_record: RunRecord
    mode: str = "design"
    audience: str = "architect"
    terminal_state: str = "DEPLOYED"
    account_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    @property
    def run_id(self) -> str:
        return self.run_record.run_id

    @property
    def spec_hash(self) -> str:
        return self.run_record.spec_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_record": self.run_record.to_dict(),
            "mode": self.mode,
            "audience": self.audience,
            "terminal_state": self.terminal_state,
            "account_id": self.account_id,
            "payload": self.payload,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredRun:
        run_record = RunRecord.from_dict(data["run_record"])
        return cls(
            run_record=run_record,
            mode=data.get("mode", "design"),
            audience=data.get("audience", "architect"),
            terminal_state=data.get("terminal_state", "DEPLOYED"),
            account_id=data.get("account_id"),
            payload=dict(data.get("payload", {})),
            created_at=data.get("created_at", _utc_now_iso()),
        )


@dataclass(frozen=True)
class StoredSpec:
    """Stored candidate specification snapshot."""

    spec_id: str
    spec_hash: str
    content: dict[str, Any]
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "spec_hash": self.spec_hash,
            "content": self.content,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredSpec:
        return cls(
            spec_id=data["spec_id"],
            spec_hash=data["spec_hash"],
            content=dict(data["content"]),
            created_at=data.get("created_at", _utc_now_iso()),
        )


@dataclass(frozen=True)
class StoredExplanation:
    """Stored explanation bundle (FD-06 §10). Immutably persisted."""

    bundle_id: str
    run_id: str
    audience: str
    content: dict[str, Any]
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "audience": self.audience,
            "content": self.content,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredExplanation:
        return cls(
            bundle_id=data["bundle_id"],
            run_id=data["run_id"],
            audience=data["audience"],
            content=dict(data["content"]),
            created_at=data.get("created_at", _utc_now_iso()),
        )


@dataclass(frozen=True)
class StoredWaiver:
    """Stored finding waiver (FD-02 §7)."""

    waiver_id: str
    finding_id: str
    run_id: str
    user_ref: str
    justification: str
    expires_at: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "waiver_id": self.waiver_id,
            "finding_id": self.finding_id,
            "run_id": self.run_id,
            "user_ref": self.user_ref,
            "justification": self.justification,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredWaiver:
        return cls(
            waiver_id=data["waiver_id"],
            finding_id=data["finding_id"],
            run_id=data["run_id"],
            user_ref=data["user_ref"],
            justification=data["justification"],
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at", _utc_now_iso()),
        )


INIT_DB_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    spec_hash TEXT NOT NULL,
    graph_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    seed INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'design',
    audience TEXT NOT NULL DEFAULT 'architect',
    terminal_state TEXT NOT NULL DEFAULT 'DEPLOYED',
    account_id TEXT,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_spec_hash ON runs(spec_hash);
CREATE INDEX IF NOT EXISTS idx_runs_account_id ON runs(account_id);
CREATE INDEX IF NOT EXISTS idx_runs_mode ON runs(mode);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);

CREATE TABLE IF NOT EXISTS specifications (
    spec_id TEXT PRIMARY KEY,
    spec_hash TEXT NOT NULL UNIQUE,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS explanations (
    bundle_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    audience TEXT NOT NULL,
    content_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_explanations_run_id ON explanations(run_id);

CREATE TABLE IF NOT EXISTS waivers (
    waiver_id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    user_ref TEXT NOT NULL,
    justification TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_waivers_finding_id ON waivers(finding_id);
CREATE INDEX IF NOT EXISTS idx_waivers_run_id ON waivers(run_id);
"""
