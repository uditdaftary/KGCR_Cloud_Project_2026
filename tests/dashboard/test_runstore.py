"""Stored runs read back the same way for the CLI and the dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from kgcr.cli import main  # noqa: E402
from kgcr.explainer.explainer import ExplanationBundle, bundle_json  # noqa: E402
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier  # noqa: E402
from kgcr.orchestration.review import run_review  # noqa: E402
from kgcr.orchestration.runstore import RunNotFound, list_runs, load_run  # noqa: E402


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("store")
    run_review(
        variant="unencrypted_database",
        store=LocalArtifactStore(root),
        notifier=LogNotifier(),
        llm=None,
        count=60,
    )
    return root


def test_review_stores_summary_and_timings(store: Path) -> None:
    run_dir = next((store / "runs").iterdir())
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["variant"] == "unencrypted_database" and summary["severity"] == "CRITICAL"
    addresses = {n["address"] for n in summary["graph"]["nodes"]}
    assert all(s in addresses and t in addresses for s, t in summary["graph"]["edges"])
    assert summary["loop"]["passes"] and summary["llm_mode"] == "disabled"
    stages = [t["stage"] for t in json.loads((run_dir / "timings.json").read_text("utf-8"))]
    assert stages == ["harvest", "graph", "intent", "recommend", "advise", "explain"]


def test_review_stores_mode_and_the_observed_spec(store: Path) -> None:
    run_dir = next((store / "runs").iterdir())
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    observed = json.loads((run_dir / "observed_spec.tf.json").read_text(encoding="utf-8"))
    patched = json.loads((run_dir / "patched_spec.tf.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "review"
    # The observed estate is the defected one; the patched spec is what the loop settled on.
    assert observed["resource"] != patched["resource"]
    assert list_runs(store)[0]["mode"] == "review"


def test_a_run_stored_without_a_mode_still_lists_as_a_review(store: Path, tmp_path: Path) -> None:
    import shutil

    old = tmp_path / "old"
    shutil.copytree(store, old)
    for summary_path in (old / "runs").glob("*/summary.json"):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        del summary["mode"]
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
    for observed_path in (old / "runs").glob("*/observed_spec.tf.json"):
        observed_path.unlink()
    rows = list_runs(old)
    assert rows and rows[0]["mode"] == "review"
    assert load_run(old, rows[0]["prefix"])["summary"] is not None


def test_bundle_round_trips_through_from_dict(store: Path) -> None:
    text = next((store / "runs").glob("*/bundle.json")).read_text(encoding="utf-8")
    assert bundle_json(ExplanationBundle.from_dict(json.loads(text))) == text


def test_load_run_rerenders_and_pins_identical_claims(store: Path) -> None:
    prefix = list_runs(store)[0]["prefix"]
    run = load_run(store, prefix[:6])
    assert run["prefix"] == prefix and run["summary"] is not None
    claims = list(run["claims"].values())
    assert claims[0] and all(c == claims[0] for c in claims)
    for audience, text in run["explanations"].items():
        stored = (store / "runs" / prefix / f"explanation_{audience}.md").read_text("utf-8")
        assert text == stored


@pytest.mark.parametrize("bad", ["../etc", "zzzz", "", "a"])
def test_resolve_refuses_non_ids(store: Path, bad: str) -> None:
    with pytest.raises(RunNotFound):
        load_run(store, bad)


def test_cli_history_and_explain(store: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["history", "--out", str(store), "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows and rows[0]["variant"] == "unencrypted_database"
    assert (
        main(["explain", "--run", rows[0]["prefix"], "--audience", "auditor", "--out", str(store)])
        == 0
    )
    assert "PCI-DSS-4.0-3.5.1" in capsys.readouterr().out
    assert main(["explain", "--run", "ffff", "--out", str(store)]) == 2


def test_light_load_skips_the_renderings(store: Path) -> None:
    prefix = list_runs(store)[0]["prefix"]
    light = load_run(store, prefix, render_explanations=False)
    assert light["explanations"] == {} and light["claims"] == {}
    assert light["summary"] is not None and light["bundle"]["findings"] is not None
