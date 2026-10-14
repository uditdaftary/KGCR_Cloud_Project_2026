"""Acquisition for corpus D: clone read-only, read the licence, pin the commit, register.

Nothing is vendored. The clones live under ``dataset/raw/corpus_d/`` (git-ignored); only the
manifest of provenance is committed. A licence that is not on the accepted list is refused by
:class:`AdversarialRegistry`, and an unrecognised licence text is refused here: both fail
loudly rather than letting a repository in by default.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from kgcr.defects.adversarial import AdversarialArtifact

__all__ = ["REPOSITORIES", "acquire", "detect_licence"]

# artifact id, clone URL, the defect classes it is expected to exercise (for bookkeeping only).
REPOSITORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "terragoat",
        "https://github.com/bridgecrewio/terragoat.git",
        ("DF-1", "DF-2", "DF-3", "DF-4"),
    ),
    ("cloudgoat", "https://github.com/RhinoSecurityLabs/cloudgoat.git", ("DF-1", "DF-3", "DF-7")),
)


def detect_licence(text: str) -> str | None:
    """The SPDX id for the licence texts this project accepts; None if not recognised."""
    t = " ".join(text.lower().split())
    if "apache license" in t and "version 2.0" in t:
        return "Apache-2.0"
    if "bsd 3-clause" in t or (
        "redistribution and use in source and binary forms" in t and "neither the name" in t
    ):
        return "BSD-3-Clause"
    if "permission is hereby granted, free of charge" in t:
        return "MIT"
    return None


def _git(args: list[str], cwd: Path) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def acquire(
    artifact_id: str, url: str, defects: tuple[str, ...], root: Path
) -> AdversarialArtifact:
    """Clone ``url`` shallowly under ``root`` if absent, and return its registered provenance."""
    root.mkdir(parents=True, exist_ok=True)
    target = root / artifact_id
    if not target.exists():
        # --depth 1: only the files at the pinned commit; nothing is checked out beyond that.
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(target)], check=True, cwd=root
        )
    licence_file = next(
        (p for p in target.iterdir() if p.name.upper().startswith(("LICENSE", "LICENCE"))), None
    )
    if licence_file is None:
        raise ValueError(f"{artifact_id}: the repository has no LICENSE file")
    licence = detect_licence(licence_file.read_text(encoding="utf-8", errors="replace"))
    if licence is None:
        raise ValueError(
            f"{artifact_id}: {licence_file.name} is not a licence this project accepts"
        )
    commit = _git(["rev-parse", "HEAD"], target)
    committed = _git(["log", "-1", "--format=%cs"], target)
    # AdversarialArtifact refuses a non-permissive licence in its constructor.
    return AdversarialArtifact(
        artifact_id=artifact_id,
        source=url.removesuffix(".git"),
        licence=licence,
        provenance_url=url,
        provenance_ref=commit,
        defect_classes=defects,
        notes=f"commit dated {committed}; retrieved {datetime.now(UTC).date().isoformat()}; "
        "licence read from the repository's own LICENSE file; parsed only, never executed",
    )
