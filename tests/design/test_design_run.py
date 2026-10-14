"""Design mode end to end, and through the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from kgcr.advisor.advisor import Advisor, render_prompt  # noqa: E402
from kgcr.cli import main  # noqa: E402
from kgcr.design.intake import build_intent  # noqa: E402
from kgcr.design.synthesize import intent_values  # noqa: E402
from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier  # noqa: E402
from kgcr.orchestration.design import run_design  # noqa: E402
from kgcr.orchestration.lifecycle import read_events  # noqa: E402
from kgcr.orchestration.runstore import list_runs, load_run  # noqa: E402

STATED = {
    "archetype": "payments_api",
    "region": "eu-west-1",
    "az_spread": "two_az",
    "network_layout": "public_private",
    "logging": "full",
    "iam_shape": "least_privilege",
    "tagging": "strict",
    "scale": "small",
}
INTENT = build_intent(STATED)


class SpyLLM:
    """Records every prompt the advisor sends and answers with no findings."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str, label: str) -> str:
        self.prompts.append(prompt)
        return "[]"


@pytest.fixture(scope="module")
def stored(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, object, SpyLLM]:
    root = tmp_path_factory.mktemp("design-store")
    spy = SpyLLM()
    run = run_design(
        intent=INTENT, store=LocalArtifactStore(root), notifier=LogNotifier(), llm=spy, count=60
    )
    return root, run, spy


def test_a_design_run_is_stored_as_a_design(stored) -> None:  # type: ignore[no-untyped-def]
    root, run, _ = stored
    prefix = run.record.run_id[:16]
    summary = json.loads((root / "runs" / prefix / "summary.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "design" and summary["variant"] is None
    assert summary["intent"]["source"] == "stated"
    assert summary["intent"]["fields"]["scale"] == {"value": "small", "confidence": None}
    assert not (root / "runs" / prefix / "observed_spec.tf.json").exists()
    assert [e["event"] for e in read_events(root / "runs" / prefix)] == ["designed"]
    row = next(r for r in list_runs(root) if r["prefix"] == prefix)
    assert row["mode"] == "design"
    assert load_run(root, prefix)["summary"]["mode"] == "design"


def test_a_clean_skeleton_converges_without_findings(stored) -> None:  # type: ignore[no-untyped-def]
    _, run, _ = stored
    assert run.loop.status == "CONVERGED" and run.reviewed_findings == ()


def test_the_advisor_prompt_depends_only_on_spec_intent_and_controls(stored) -> None:  # type: ignore[no-untyped-def]
    # INV-7: nothing from the recommender (scores, options, the audit) is in the prompt.
    _, run, spy = stored
    assert spy.prompts
    expected = render_prompt(
        run.candidate.estate, intent_values(INTENT), Advisor().controls, (), ""
    )
    assert spy.prompts[0] == expected


def test_cli_design_prints_the_stages_and_stores_the_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["design", "--count", "60", "--out", str(tmp_path)]
    for axis, value in STATED.items():
        argv += [f"--{axis.replace('_', '-')}", value]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "[1/5] intake" in out and "stored bundle:" in out
    assert len(list(tmp_path.glob("runs/*/bundle.json"))) == 1


def test_cli_design_with_a_missing_axis_exits_2_and_names_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["design", "--out", str(tmp_path)]
    for axis, value in STATED.items():
        if axis != "scale":
            argv += [f"--{axis.replace('_', '-')}", value]
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert "missing: scale" in err and "small, medium, large" in err
    assert not (tmp_path / "runs").exists()
