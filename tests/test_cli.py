"""The CLI surface must exist and behave predictably even before subsystems do."""

from __future__ import annotations

import json

import pytest

from kgcr._version import __version__
from kgcr.cli import EXIT_NOT_IMPLEMENTED, main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("command", ["design", "review", "explain", "plan", "apply"])
def test_planned_commands_exit_not_implemented(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command]) == EXIT_NOT_IMPLEMENTED
    assert "not implemented" in capsys.readouterr().err.lower()


def test_repro_info_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["repro-info"]) == 0
    out = capsys.readouterr().out
    assert "seed:" in out
    assert "tool versions:" in out


def test_repro_info_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["repro-info", "--json", "--seed", "5"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["seed_report"]["seed"] == 5
    assert payload["tool_versions"]["kgcr"] == __version__


def test_corpus_json_summary(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["corpus", "--count", "20", "--seed", "1", "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["estates"] == 20
    assert summary["unique_estate_ids"] == 20


def test_corpus_writes_to_directory(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "corpus"
    assert main(["corpus", "--count", "8", "--out", str(out)]) == 0
    assert (out / "manifest.json").exists()
    assert "written to:" in capsys.readouterr().out


def test_history_cli(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    from kgcr.persistence import SQLiteRunStore, StoredRun
    from kgcr.runrecord import RunRecord

    db_path = str(tmp_path / "history_test.db")
    store = SQLiteRunStore(db_path)
    rr = RunRecord(spec_hash="cli_test_hash", graph_version="v1", model_version="v1", seed=42)
    store.save_run(StoredRun(run_record=rr, account_id="acc-cli-123"))
    store.close()

    # Query all runs via CLI
    assert main(["history", "--db", db_path]) == 0
    out = capsys.readouterr().out
    assert "Found 1 run record(s):" in out

    # Query with --json
    assert main(["history", "--db", db_path, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    assert payload[0]["account_id"] == "acc-cli-123"

    # Query by run_id
    assert main(["history", "--db", db_path, "--run-id", rr.run_id]) == 0
    out_id = capsys.readouterr().out
    assert "run_id:" in out_id
    assert "cli_test_hash" in out_id
