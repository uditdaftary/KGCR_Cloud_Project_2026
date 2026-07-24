"""Run records must round-trip and identify by the reproducibility triple."""

from __future__ import annotations

import pytest

from kgcr.runrecord import RunRecord


def _record(**overrides: object) -> RunRecord:
    base: dict[str, object] = {
        "spec_hash": "abc123",
        "graph_version": "L1-2026.07",
        "model_version": "advisor-v0",
    }
    base.update(overrides)
    return RunRecord(**base)  # type: ignore[arg-type]


def test_run_id_is_deterministic_over_triple_and_seed() -> None:
    a = _record()
    b = _record()
    assert a.run_id == b.run_id


def test_run_id_ignores_created_at() -> None:
    a = _record(created_at="2026-01-01T00:00:00+00:00")
    b = _record(created_at="2026-07-24T00:00:00+00:00")
    assert a.run_id == b.run_id


def test_run_id_changes_with_any_triple_field() -> None:
    base = _record().run_id
    assert _record(spec_hash="different").run_id != base
    assert _record(graph_version="L1-2027.01").run_id != base
    assert _record(model_version="advisor-v1").run_id != base
    assert _record(seed=99).run_id != base


def test_json_round_trip_preserves_record() -> None:
    original = _record(seed=7)
    restored = RunRecord.from_json(original.to_json())
    assert restored == original
    assert restored.run_id == original.run_id


def test_from_dict_rejects_tampered_run_id() -> None:
    data = _record().to_dict()
    data["run_id"] = "0" * 64
    with pytest.raises(ValueError, match="run_id mismatch"):
        RunRecord.from_dict(data)


def test_save_and_load_round_trip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    original = _record()
    path = original.save(tmp_path / "run.json")
    assert path.exists()
    assert RunRecord.load(path) == original


def test_tool_versions_include_kgcr_and_python() -> None:
    record = _record()
    assert "kgcr" in record.tool_versions
    assert "python" in record.tool_versions
