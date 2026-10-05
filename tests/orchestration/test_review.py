"""The local review pipeline runs end to end and its run identity is reproducible."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from kgcr.cli import main  # noqa: E402
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier  # noqa: E402
from kgcr.orchestration.review import run_review  # noqa: E402


def test_review_patches_a_rule_defect_and_stores_every_artifact(tmp_path: Path) -> None:
    run = run_review(
        variant="unencrypted_database",
        store=LocalArtifactStore(tmp_path),
        notifier=LogNotifier(),
        count=60,
    )
    assert (run.loop.status, run.loop.reason) == ("CONVERGED", "CLEAN")
    assert [f.control_node for f in run.reviewed_findings] == ["kg://control/pci-dss-v4/3.5.1"]
    assert run.bundle.findings[0].counterfactual is not None
    assert run.bundle.findings[0].counterfactual.resolved
    for uri in run.artifacts.values():
        assert Path(uri).is_file(), uri
    bundle = json.loads(Path(run.artifacts["bundle"]).read_text(encoding="utf-8"))
    assert "rule floor only" in bundle["scope_note"]  # no LLM in this test


def test_run_identity_is_stable_across_reruns(tmp_path: Path) -> None:
    kwargs = {"variant": "unencrypted_database", "notifier": LogNotifier(), "count": 60}
    first = run_review(store=LocalArtifactStore(tmp_path / "a"), **kwargs)  # type: ignore[arg-type]
    second = run_review(store=LocalArtifactStore(tmp_path / "b"), **kwargs)  # type: ignore[arg-type]
    assert first.record.run_id == second.record.run_id


def test_store_refuses_keys_that_escape_its_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        LocalArtifactStore(tmp_path).put("../outside.json", "{}")


def test_cli_review_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["review", "--variant", "unencrypted_database", "--count", "60", "--out", str(tmp_path)]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "[6/6] explain" in out and "PCI-DSS-4.0-3.5.1" in out
