"""Licence-tracked registry for the adversarial corpus (corpus D, FD-05 §4D).

Corpus D (CloudGoat, TerraGoat, flaws.cloud, and comparable deliberately-
vulnerable environments) provides independently-authored known-bad configs, so
recall against them is meaningful in a way self-injected recall is not (FD-05
§7, Defence). Because the project did not author these, licensing must be
accounted for **per artifact** — FD-05 §4B: "An academic project that cannot
account for the licensing of its corpus has a problem that no amount of model
performance repairs."

This module is the *tracking* half only. It records source, provenance, and
licence per artifact and **refuses** any artifact under a non-permissive licence
— failing loud, not silently including it. It does **not** fetch anything:
cloning the upstream repos, verifying each repo's actual licence, and pinning a
commit is a separate data-acquisition step, deliberately kept out of the code
path so no unlicensed content is ever vendored by accident.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ACCEPTED_LICENCES", "AdversarialArtifact", "AdversarialRegistry"]

# Permissive licences accepted for corpus D (FD-05 §4B: Apache-2.0, MIT, or an
# explicit AWS sample licence). SPDX identifiers, plus the AWS sample marker.
ACCEPTED_LICENCES: frozenset[str] = frozenset(
    {
        "Apache-2.0",
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "AWS-Sample",
    }
)


@dataclass(frozen=True, slots=True)
class AdversarialArtifact:
    """One imported known-bad artifact with its provenance and licence.

    ``provenance`` pins where it came from precisely enough to re-fetch: a repo
    URL plus a commit or tag. ``licence`` must be an SPDX id in
    :data:`ACCEPTED_LICENCES`. ``defect_classes`` names the DF-n classes the
    artifact is expected to exercise, for recall bookkeeping.
    """

    artifact_id: str
    source: str
    licence: str
    provenance_url: str
    provenance_ref: str
    defect_classes: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if self.licence not in ACCEPTED_LICENCES:
            raise ValueError(
                f"artifact {self.artifact_id!r} has non-permissive licence {self.licence!r}; "
                f"accepted: {sorted(ACCEPTED_LICENCES)}"
            )
        if not self.provenance_url or not self.provenance_ref:
            raise ValueError(f"artifact {self.artifact_id!r} must record provenance (url and ref)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "source": self.source,
            "licence": self.licence,
            "provenance_url": self.provenance_url,
            "provenance_ref": self.provenance_ref,
            "defect_classes": list(self.defect_classes),
            "notes": self.notes,
        }


@dataclass
class AdversarialRegistry:
    """A set of adversarial artifacts, keyed by id, with licence enforced on add."""

    artifacts: dict[str, AdversarialArtifact] = field(default_factory=dict)

    def add(self, artifact: AdversarialArtifact) -> None:
        if artifact.artifact_id in self.artifacts:
            raise ValueError(f"duplicate artifact id: {artifact.artifact_id!r}")
        self.artifacts[artifact.artifact_id] = artifact

    def to_manifest(self) -> dict[str, Any]:
        """A deterministic manifest of the corpus D provenance."""
        return {
            "count": len(self.artifacts),
            "licences": sorted({a.licence for a in self.artifacts.values()}),
            "artifacts": [a.to_dict() for a in sorted(self.artifacts.values(), key=_key)],
        }

    def write_manifest(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_manifest(), indent=2, sort_keys=True), encoding="utf-8")
        return out


def _key(artifact: AdversarialArtifact) -> str:
    return artifact.artifact_id
