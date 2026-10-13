"""The dashboard's store, job validation, child environment and HTTP guards.

No test here starts a job: the runner would spawn a subprocess. Validation and the
environment a job would get are tested directly instead.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kgcr.dashboard.db import FIRST_CATALOG_NO, Database
from kgcr.dashboard.jobs import JobError, Runner, _run_prefix, validate
from kgcr.dashboard.server import make_server

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
    assert params["seed"] == 1729 and params["count"] == 180 and live is False


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


def test_child_environment_withholds_secrets_unless_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("KGCR_LLM_LIVE", "1")  # what .env sets on the operator's machine
    runner = Runner(Database(tmp_path / "d.sqlite3"), tmp_path)
    replay = runner._env(live=False)
    assert replay["KGCR_LLM_LIVE"] == "0" and replay["PYTHONHASHSEED"] == "0"
    assert "GEMINI_API_KEY" not in replay and "AWS_SECRET_ACCESS_KEY" not in replay
    live = runner._env(live=True)
    assert live["KGCR_LLM_LIVE"] == "1" and live["GEMINI_API_KEY"] == "secret"


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
