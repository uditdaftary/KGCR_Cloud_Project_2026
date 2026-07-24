"""Canonical hashing of JSON-serialisable objects.

The reproducibility track (PMD) requires that a run re-derive from a stable
``spec hash``. A stable hash is only possible if the same logical object always
serialises to the same bytes, regardless of dict insertion order or
whitespace. :func:`canonical_json` produces that byte-stable form and
:func:`canonical_hash` hashes it.

This also underpins the Phase 1 "canonical-hash stability" test on the ontology
encoding: two encodings that are equal as data must hash equal.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["canonical_json", "canonical_hash"]


def canonical_json(obj: Any) -> str:
    """Serialise ``obj`` to a canonical JSON string.

    Keys are sorted, separators are compact, and non-ASCII characters are kept
    verbatim (``ensure_ascii=False``) so that the encoding is stable and
    independent of dict insertion order.

    Raises ``TypeError`` if ``obj`` contains a non-JSON-serialisable value; we
    deliberately do not fall back to ``str`` so that an unhashable input fails
    loudly rather than hashing to something meaningless.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def canonical_hash(obj: Any, *, algorithm: str = "sha256") -> str:
    """Return the hex digest of the canonical serialisation of ``obj``.

    ``algorithm`` is any name accepted by :func:`hashlib.new`. The default,
    sha256, is the project standard for spec and graph hashes.
    """
    digest = hashlib.new(algorithm)
    digest.update(canonical_json(obj).encode("utf-8"))
    return digest.hexdigest()
