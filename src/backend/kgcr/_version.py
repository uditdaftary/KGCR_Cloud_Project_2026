"""Single source of truth for the package version.

Kept in sync with ``pyproject.toml``. The version is part of every run record
(see :mod:`kgcr.runrecord`) so that a result can be tied back to the code that
produced it.
"""

from __future__ import annotations

__version__ = "0.0.0"
