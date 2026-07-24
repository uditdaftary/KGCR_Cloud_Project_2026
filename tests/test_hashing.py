"""Canonical hashing must be stable and order-independent."""

from __future__ import annotations

import pytest

from kgcr.hashing import canonical_hash, canonical_json


def test_key_order_does_not_change_hash() -> None:
    a = {"framework": "PCI-DSS", "severity": "critical", "hop_bound": 3}
    b = {"hop_bound": 3, "severity": "critical", "framework": "PCI-DSS"}
    assert canonical_hash(a) == canonical_hash(b)


def test_nested_order_does_not_change_hash() -> None:
    a = {"controls": [{"id": "1.1", "sev": "high"}, {"id": "1.2", "sev": "low"}]}
    b = {"controls": [{"sev": "high", "id": "1.1"}, {"sev": "low", "id": "1.2"}]}
    assert canonical_hash(a) == canonical_hash(b)


def test_distinct_values_hash_differently() -> None:
    assert canonical_hash({"sev": "high"}) != canonical_hash({"sev": "low"})


def test_canonical_json_is_compact_and_sorted() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_hash_is_stable_literal() -> None:
    # A frozen expectation: canonical_hash({"a": 1}) is sha256 of the exact
    # bytes b'{"a":1}'. If this drifts, the canonicalisation changed and every
    # previously recorded spec hash would silently invalidate.
    import hashlib

    expected = hashlib.sha256(b'{"a":1}').hexdigest()
    assert canonical_hash({"a": 1}) == expected


def test_unserialisable_input_raises() -> None:
    with pytest.raises(TypeError):
        canonical_hash({"bad": object()})
