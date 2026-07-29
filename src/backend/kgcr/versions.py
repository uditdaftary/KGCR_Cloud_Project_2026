"""Capture the versions that a run depends on.

A result is only reproducible if we record *what* produced it. This module
collects the version fingerprint that goes into every run record: the KGCR
package version, the Python version, and the versions of any
reproducibility-relevant libraries that happen to be installed.

Libraries are probed defensively — the scaffolding does not depend on torch,
numpy, or neo4j, but when a later phase installs them their versions are
captured automatically without this module needing to change.
"""

from __future__ import annotations

import platform
from importlib import metadata

from kgcr._version import __version__

__all__ = ["tool_versions", "REPRODUCIBILITY_RELEVANT"]

# Distributions whose version materially affects a result. Absent ones are
# simply omitted from the fingerprint rather than reported as an error.
REPRODUCIBILITY_RELEVANT: tuple[str, ...] = (
    "numpy",
    "torch",
    "torch-geometric",
    "scikit-learn",
    "neo4j",
    "PyYAML",
)


def _distribution_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def tool_versions() -> dict[str, str]:
    """Return the version fingerprint for the current environment.

    Always includes ``kgcr`` and ``python``. Includes each entry of
    :data:`REPRODUCIBILITY_RELEVANT` that is installed, keyed by distribution
    name. The result is deterministic for a fixed environment and safe to embed
    in a canonical hash.
    """
    versions: dict[str, str] = {
        "kgcr": __version__,
        "python": platform.python_version(),
    }
    for name in REPRODUCIBILITY_RELEVANT:
        found = _distribution_version(name)
        if found is not None:
            versions[name] = found
    return versions
