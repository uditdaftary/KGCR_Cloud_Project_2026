"""Run records — the reproducibility unit of the framework.

PMD's reproducibility track states that every result must re-derive from
``(spec hash, graph version, model version)``. A :class:`RunRecord` is that
triple made concrete, plus the seed and the environment fingerprint, plus a
timestamp for human bookkeeping.

The ``run_id`` is a canonical hash of the *reproducibility-determining* fields
only — the triple and the seed — deliberately excluding the wall-clock
timestamp. Two runs with the same spec, graph, model, and seed therefore share
a ``run_id``: identity is defined by what determines the result, not by when it
happened. This is what lets P11's "re-derive a run from its identifiers"
regression check work.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kgcr.hashing import canonical_hash
from kgcr.repro import DEFAULT_SEED
from kgcr.versions import tool_versions

__all__ = ["RunRecord"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RunRecord:
    """An immutable record identifying one run of the pipeline.

    ``spec_hash`` is the canonical hash of the input spec; ``graph_version`` and
    ``model_version`` identify the frozen ontology/graph and the model in use.
    ``created_at`` is informational only and never affects ``run_id``.
    """

    spec_hash: str
    graph_version: str
    model_version: str
    seed: int = DEFAULT_SEED
    tool_versions: dict[str, str] = field(default_factory=tool_versions)
    created_at: str = field(default_factory=_utc_now_iso)

    @property
    def run_id(self) -> str:
        """Deterministic identifier over the reproducibility-determining fields."""
        return canonical_hash(
            {
                "spec_hash": self.spec_hash,
                "graph_version": self.graph_version,
                "model_version": self.model_version,
                "seed": self.seed,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict, with ``run_id`` included for readers."""
        return {
            "run_id": self.run_id,
            "spec_hash": self.spec_hash,
            "graph_version": self.graph_version,
            "model_version": self.model_version,
            "seed": self.seed,
            "tool_versions": dict(self.tool_versions),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        """Rebuild a record from :meth:`to_dict` output.

        A ``run_id`` present in ``data`` is treated as derived and ignored; if
        present it must match the recomputed value, otherwise the record has
        been tampered with or was written by an incompatible version.
        """
        record = cls(
            spec_hash=data["spec_hash"],
            graph_version=data["graph_version"],
            model_version=data["model_version"],
            seed=data.get("seed", DEFAULT_SEED),
            tool_versions=dict(data.get("tool_versions", {})),
            created_at=data.get("created_at", _utc_now_iso()),
        )
        stored = data.get("run_id")
        if stored is not None and stored != record.run_id:
            raise ValueError(f"run_id mismatch: stored {stored!r} != recomputed {record.run_id!r}")
        return record

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> RunRecord:
        return cls.from_dict(json.loads(text))

    def save(self, path: str | Path) -> Path:
        """Write the record as JSON, returning the path written."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_json(), encoding="utf-8")
        return out

    @classmethod
    def load(cls, path: str | Path) -> RunRecord:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))
