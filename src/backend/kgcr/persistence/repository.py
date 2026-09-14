"""Abstract base repository interface for persistence operations (FD-03, FD-06)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from kgcr.persistence.schema import (
    StoredExplanation,
    StoredRun,
    StoredSpec,
    StoredWaiver,
)

__all__ = ["RunRepository"]


class RunRepository(ABC):
    """Abstract interface defining operations for storing and querying pipeline artifacts."""

    @abstractmethod
    def save_run(self, run: StoredRun) -> str:
        """Persist a run record and its metadata. Returns the run_id."""

    @abstractmethod
    def get_run(self, run_id: str) -> StoredRun | None:
        """Fetch a run record by run_id."""

    @abstractmethod
    def list_runs(
        self,
        *,
        account_id: str | None = None,
        mode: str | None = None,
        terminal_state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StoredRun]:
        """Query stored runs with optional filters."""

    @abstractmethod
    def save_spec(self, spec: StoredSpec) -> str:
        """Persist a candidate specification. Returns the spec_id."""

    @abstractmethod
    def get_spec(self, spec_id_or_hash: str) -> StoredSpec | None:
        """Fetch a specification by spec_id or spec_hash."""

    @abstractmethod
    def save_explanation(self, explanation: StoredExplanation) -> str:
        """Persist an explanation bundle (FD-06 §10). Returns bundle_id."""

    @abstractmethod
    def get_explanation(self, run_id: str, audience: str | None = None) -> StoredExplanation | None:
        """Fetch an explanation bundle for a run."""

    @abstractmethod
    def save_waiver(self, waiver: StoredWaiver) -> str:
        """Persist a finding waiver (FD-02 §7). Returns waiver_id."""

    @abstractmethod
    def list_waivers(
        self, *, run_id: str | None = None, finding_id: str | None = None
    ) -> Sequence[StoredWaiver]:
        """Query stored waivers by run_id or finding_id."""
