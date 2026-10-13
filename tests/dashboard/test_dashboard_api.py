"""The dashboard's store, job validation, child environment and HTTP guards.

Runner tests start real subprocesses, but only a stand-in ``python -c`` command registered
under a fake job kind; no repo script (review, training, the CI gates) is ever launched.
Validation and the environment a job would get are tested directly.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kgcr.dashboard.db import FIRST_CATALOG_NO, Database
from kgcr.dashboard.jobs import JOB_KINDS, JobError, JobKind, Runner, _run_prefix, validate
from kgcr.dashboard.server import make_server
from kgcr.orchestration.runstore import RunNotFound, list_runs, load_run
from kgcr.repro import DEFAULT_COUNT, DEFAULT_SEED

# --- database ------------------------------------------------------------------------


def test_catalog_starts_at_100_and_is_shared_by_sessions_and_jobs(tmp_path: Path) -> None:
    db = Database(tmp_path / "d.sqlite3")
    s = db.create_session("user")
    job = db.job(db.create_job(s["id"], "review", {"variant": "x"}, live=False))
    assert s["catalog_no"] == FIRST_CATALOG_NO
    assert job is not None and job["catalog_no"] == FIRST_CATALOG_NO + 1
    assert job["status"] == "queued" and job["params"] == {"variant": "x"}


def test_reopening_fails_jobs_the_previous_server_left_running(tmp_path: Path) -> None:
    path = tmp_path / "d.sqlite3"
    db = Database(path)
    s = db.create_session("admin")
    job_id = db.create_job(s["id"], "gates", {}, live=False)
    db.update_job(job_id, status="running")
    reopened = Database(path)
    job = reopened.job(job_id)
    assert job is not None and job["status"] == "failed"
    assert "server stopped" in job["log"]
    assert reopened.create_session("user")["catalog_no"] == FIRST_CATALOG_NO + 2


def test_update_job_refuses_unknown_columns(tmp_path: Path) -> None:
    db = Database(tmp_path / "d.sqlite3")
    with pytest.raises(ValueError):
        db.update_job(1, **{"status = 'done'; --": "x"})


def test_role_is_constrained(tmp_path: Path) -> None:
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        Database(tmp_path / "d.sqlite3").create_session("root")


# --- validation ----------------------------------------------------------------------


def test_user_review_gets_defaults_and_stays_replay() -> None:
    params, live = validate("review", {}, role="user", live_enabled=True)
    assert params["seed"] == DEFAULT_SEED and params["count"] == DEFAULT_COUNT
    assert live is False


@pytest.mark.parametrize(
    ("kind", "raw", "role", "live_enabled", "message"),
    [
        ("nope", {}, "admin", False, "unknown job"),
        ("gates", {}, "user", False, "admin job"),
        ("review", {"live": True}, "user", True, "admin only"),
        ("review", {"live": True}, "admin", False, "switched off"),
        ("review", {"s3_bucket": "my-bucket"}, "admin", False, "switched off"),
        ("review", {"s3_bucket": "Bad_Bucket!"}, "admin", True, "not a valid"),
        ("review", {"sns_topic_arn": "arn:aws:sns:x"}, "admin", True, "not a valid"),
        ("review", {"variant": "rm -rf /"}, "user", False, "must be one of"),
        ("review", {"count": 5}, "user", False, "between"),
        ("review", {"count": True}, "user", False, "whole number"),
        ("review", {"extra": 1}, "user", False, "unknown parameter"),
        ("review", {"s3_bucket": "my-bucket\n"}, "admin", True, "not a valid"),
    ],
)
def test_validation_refuses(
    kind: str, raw: dict[str, Any], role: str, live_enabled: bool, message: str
) -> None:
    with pytest.raises(JobError, match=message):
        validate(kind, raw, role=role, live_enabled=live_enabled)


def test_cloud_targets_count_as_live_once_enabled() -> None:
    arn = "arn:aws:sns:eu-west-1:123456789012:kgcr-contested"
    params, live = validate("review", {"sns_topic_arn": arn}, role="admin", live_enabled=True)
    assert live is True and params["sns_topic_arn"] == arn


def test_train_job_uses_the_corpus_seed_the_recorded_result_used() -> None:
    params, _ = validate("reconstruction_train", {}, role="admin", live_enabled=False)
    assert params["seed"] == DEFAULT_SEED


def test_child_environment_blanks_secrets_unless_granted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("KGCR_LLM_LIVE", "1")  # what .env sets on the operator's machine
    runner = Runner(Database(tmp_path / "d.sqlite3"), tmp_path)
    replay = runner.child_env(live=False)
    assert replay["KGCR_LLM_LIVE"] == "0" and replay["PYTHONHASHSEED"] == "0"
    # Blank, not absent: the child's load_dotenv(override=False) would refill an absent name.
    assert replay["GEMINI_API_KEY"] == "" and replay["AWS_SECRET_ACCESS_KEY"] == ""
    live = runner.child_env(live=True)
    assert live["KGCR_LLM_LIVE"] == "1" and live["GEMINI_API_KEY"] == "secret"
    assert live["AWS_SECRET_ACCESS_KEY"] == ""  # a Gemini job gets no AWS credentials
    cloud = runner.child_env(live=False, cloud=True)
    assert cloud["KGCR_LLM_LIVE"] == "0" and cloud["GEMINI_API_KEY"] == ""
    assert cloud["AWS_SECRET_ACCESS_KEY"] == "secret"


def test_run_prefix_is_read_from_the_review_log() -> None:
    log = "      stored bundle: runs-local\\runs\\9d9d36ac2777abf5\\bundle.json\n"
    assert _run_prefix(log) == "9d9d36ac2777abf5"
    assert _run_prefix("no bundle here") is None


# --- HTTP ----------------------------------------------------------------------------


@pytest.fixture
def base(tmp_path: Path) -> Iterator[str]:
    server = make_server(0, tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def call(url: str, body: Any = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        # Generous: the first request pays cold imports, slow on a loaded machine.
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read()
            ctype = res.headers.get("Content-Type", "")
            return res.status, json.loads(raw) if "json" in ctype else raw
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


DASH = {"Content-Type": "application/json", "X-KGCR": "1"}


def test_meta_and_static_page_are_served(base: str) -> None:
    status, meta = call(f"{base}/api/meta")
    assert status == 200 and meta["live_enabled"] is False and meta["live_call_cap"] == 24
    assert {p["command"] for p in meta["planned"]} == {"design", "plan", "apply"}
    status, page = call(f"{base}/")
    assert status == 200 and b"app.js" in page


def test_foreign_host_header_is_refused(base: str) -> None:
    status, body = call(f"{base}/api/meta", headers={"Host": "evil.example:80"})
    assert status == 403 and "Host" in body["error"]


def test_post_without_dashboard_header_is_refused(base: str) -> None:
    status, _ = call(
        f"{base}/api/sessions", {"role": "admin"}, {"Content-Type": "application/json"}
    )
    assert status == 403


def test_session_then_jobs_and_live_switch(base: str) -> None:
    status, user = call(f"{base}/api/sessions", {"role": "user"}, DASH)
    assert status == 201
    status, body = call(f"{base}/api/jobs", {"session": user["id"], "kind": "gates"}, DASH)
    assert status == 400 and "admin job" in body["error"]
    status, body = call(f"{base}/api/admin/live", {"session": user["id"], "enabled": True}, DASH)
    assert status == 403
    _, admin = call(f"{base}/api/sessions", {"role": "admin"}, DASH)
    status, body = call(f"{base}/api/admin/live", {"session": admin["id"], "enabled": True}, DASH)
    assert status == 400  # no confirm
    status, body = call(
        f"{base}/api/admin/live", {"session": admin["id"], "enabled": True, "confirm": True}, DASH
    )
    assert status == 200 and body["live_enabled"] is True
    status, body = call(f"{base}/api/jobs", {"session": "forged", "kind": "review"}, DASH)
    assert status == 401


@pytest.mark.parametrize(
    "path",
    ["/repo/../.env", "/repo/docs/../.env", "/repo/src/backend/kgcr/cli.py", "/build_dashboard.py"],
)
def test_files_outside_the_allow_list_are_not_served(base: str, path: str) -> None:
    status, _ = call(base + path)
    assert status == 404


def test_fixture_label_is_validated(base: str) -> None:
    status, _ = call(f"{base}/api/fixtures/..%2F..%2F.env")
    assert status in (400, 404)
    status, rows = call(f"{base}/api/fixtures")
    assert status == 200
    if rows:
        status, fixture = call(f"{base}/api/fixtures/{rows[0]['label']}")
        assert status == 200 and "response" in fixture


def test_relative_store_root_is_made_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    server = make_server(0, Path("runs-local"))
    try:
        app = server.RequestHandlerClass.app  # type: ignore[attr-defined]
        assert app.store_root.is_absolute() and app.store_root == (tmp_path / "runs-local")
    finally:
        server.server_close()


@pytest.mark.parametrize("length", ["abc", "-1"])
def test_bad_content_length_is_a_400(base: str, length: str) -> None:
    port = int(base.rsplit(":", 1)[1])
    request = (
        f"POST /api/sessions HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"Content-Type: application/json\r\nX-KGCR: 1\r\nContent-Length: {length}\r\n\r\n"
    )
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(request.encode())
        assert sock.recv(64).startswith(b"HTTP/1.0 400")


# --- stored runs that are damaged ----------------------------------------------------


def test_damaged_run_is_skipped_not_fatal(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "0123456789abcdef"
    run.mkdir(parents=True)
    (run / "run_record.json").write_text("")  # what a killed write used to leave
    (run / "bundle.json").write_text("{}")
    assert list_runs(tmp_path) == []
    with pytest.raises(RunNotFound):
        load_run(tmp_path, "0123456789abcdef")
    (run / "bundle.json").unlink()
    with pytest.raises(RunNotFound):
        load_run(tmp_path, "0123")


# --- the runner, with a stand-in job kind (no repo script is started) ----------------


def _fake_kind(*code: str) -> JobKind:
    return JobKind(
        label="fake",
        summary="",
        writes="",
        argv=lambda _p, _o, _s: [[sys.executable, "-c", c] for c in code],
        admin_only=False,
    )


def _wait(db: Database, job_id: int, *states: str) -> dict[str, Any]:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = db.job(job_id)
        if job is not None and job["status"] in states:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never reached {states}")


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Runner]:
    monkeypatch.setitem(JOB_KINDS, "fake", _fake_kind("print('hello')"))
    monkeypatch.setitem(JOB_KINDS, "slow", _fake_kind("import time; time.sleep(60)"))
    monkeypatch.setitem(JOB_KINDS, "two", _fake_kind("print('one')", "raise SystemExit(3)"))
    r = Runner(Database(tmp_path / "d.sqlite3"), tmp_path)
    yield r
    r.shutdown()


def _submit(r: Runner, kind: str, live: bool = False) -> int:
    session = r.db.create_session("admin")
    job_id = r.db.create_job(session["id"], kind, {}, live)
    r.submit(job_id)
    return job_id


def test_runner_runs_a_job_and_stops_a_failing_chain(runner: Runner) -> None:
    done = _wait(runner.db, _submit(runner, "fake"), "done", "failed")
    assert done["status"] == "done" and "hello" in done["log"]
    failed = _wait(runner.db, _submit(runner, "two"), "done", "failed")
    assert failed["status"] == "failed" and failed["exit_code"] == 3


def test_cancel_stops_a_running_job_and_reports_it(runner: Runner) -> None:
    job_id = _submit(runner, "slow")
    _wait(runner.db, job_id, "running")
    deadline = time.monotonic() + 10
    while runner._procs.get(job_id) is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert runner.cancel(job_id) is True
    assert _wait(runner.db, job_id, "cancelled", "done", "failed")["status"] == "cancelled"
    assert runner.cancel(job_id) is False  # finished: nothing left to cancel


def test_live_job_is_refused_once_live_mode_is_off(runner: Runner) -> None:
    job = _wait(runner.db, _submit(runner, "fake", live=True), "cancelled", "done", "failed")
    assert job["status"] == "cancelled" and "switched off" in job["log"]


def test_shutdown_terminates_the_running_child(runner: Runner) -> None:
    job_id = _submit(runner, "slow")
    _wait(runner.db, job_id, "running")
    deadline = time.monotonic() + 10
    while runner._procs.get(job_id) is None and time.monotonic() < deadline:
        time.sleep(0.05)
    runner.shutdown()
    assert _wait(runner.db, job_id, "cancelled", "done", "failed")["status"] == "cancelled"


def test_cancelling_a_queued_job_takes_it_off_the_queue(runner: Runner) -> None:
    blocker = _submit(runner, "slow")
    _wait(runner.db, blocker, "running")
    queued = _submit(runner, "fake")
    assert runner.position(queued) == 1
    assert runner.cancel(queued) is True
    assert runner.position(queued) is None
    assert runner.db.job(queued)["status"] == "cancelled"  # type: ignore[index]


def test_job_outputs_are_read_only_when_finished_and_readable(tmp_path: Path, base: str) -> None:
    from kgcr.dashboard.server import App, job_view

    app = App(tmp_path)
    session = app.db.create_session("admin")
    job_id = app.db.create_job(session["id"], "gates", {}, live=False)
    out = tmp_path / "jobs" / "KG101"
    out.mkdir(parents=True)
    (out / "half.json").write_text('{"a":')  # as a report looks mid-write
    (out / "good.json").write_text('{"a": 1}')
    app.db.update_job(job_id, status="running", output_dir=str(out))
    assert (job_view(app, job_id) or {})["outputs"] == {}
    app.db.update_job(job_id, status="done")
    assert (job_view(app, job_id) or {})["outputs"] == {"good.json": {"a": 1}}
    app.runner.shutdown()


def test_environment_report_comes_from_a_child_and_does_not_reseed_the_server(base: str) -> None:
    import random

    random.seed(5)
    before = random.getstate()
    status, env = call(f"{base}/api/environment")
    assert status == 200 and env["error"] is None
    # What a job reports: the runner pins PYTHONHASHSEED for it, whatever this process has.
    assert env["seed_report"]["seed"] == DEFAULT_SEED and env["seed_report"]["pythonhashseed"]
    assert "kgcr" in env["tool_versions"]
    assert random.getstate() == before


def test_live_log_keeps_only_a_bounded_tail() -> None:
    from kgcr.dashboard.jobs import MAX_LOG_CHARS, _LogTail

    tail = _LogTail()
    for i in range(5000):
        tail.add(f"line {i:05d} {'x' * 90}\n")
    assert len(tail.text()) <= MAX_LOG_CHARS
    assert tail.text().endswith(f"line 04999 {'x' * 90}\n")
    tail.add("y" * (MAX_LOG_CHARS * 3))  # one enormous line is clipped too
    assert len(tail.text()) <= MAX_LOG_CHARS


def test_repo_files_are_served_sandboxed(base: str) -> None:
    with urllib.request.urlopen(f"{base}/repo/docs/Runbook.md", timeout=10) as res:
        res.read()
        assert res.status == 200 and res.headers["Content-Security-Policy"] == "sandbox"


def test_local_store_retries_while_a_reader_holds_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    from kgcr.orchestration import aws as aws_module
    from kgcr.orchestration.aws import LocalArtifactStore

    real_replace, calls = os.replace, []

    def flaky(src: Any, dst: Any) -> None:  # Windows: the dashboard has the file open
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError(5, "in use")
        real_replace(src, dst)

    monkeypatch.setattr(aws_module.os, "replace", flaky)
    LocalArtifactStore(tmp_path).put("runs/x/bundle.json", "{}")
    assert len(calls) == 3 and (tmp_path / "runs/x/bundle.json").read_text() == "{}"
    assert not list((tmp_path / "runs/x").glob("*.partial"))
