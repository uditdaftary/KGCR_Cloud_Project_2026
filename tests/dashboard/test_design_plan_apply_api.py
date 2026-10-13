"""Design, plan and apply through the dashboard: validation, the spend gate, the child
environment and the read routes. Nothing here launches a real job."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kgcr.dashboard.db import Database
from kgcr.dashboard.jobs import JobError, Runner, _run_prefix, is_cloud, validate
from kgcr.dashboard.server import make_server
from kgcr.plan.local import make_plan
from tests.dashboard.test_dashboard_api import DASH, call
from tests.plan.test_plan_local import _run

AXES = {
    "archetype": "payments_api",
    "region": "eu-west-1",
    "az_spread": "two_az",
    "network_layout": "public_private",
    "logging": "full",
    "iam_shape": "least_privilege",
    "tagging": "strict",
    "scale": "small",
}
# Recorded live on 2026-10-13: results/llm_fixtures/intent-v1-f6517e7586f2e501.json
STATEMENT = (
    "We are building a payments API that handles card data. It runs in eu-west-1 across three "
    "availability zones, with a public load balancer in front of private application subnets, "
    "full audit logging, least-privilege IAM roles and strict tagging. Start small."
)


# --- validation ----------------------------------------------------------------------


def test_design_needs_every_axis_and_never_defaults_one() -> None:
    params, live = validate("design", AXES, role="user", live_enabled=False)
    assert params["archetype"] == "payments_api" and live is False
    for axis in AXES:
        short = {k: v for k, v in AXES.items() if k != axis}
        with pytest.raises(JobError, match="must be one of"):
            validate("design", short, role="user", live_enabled=False)
    with pytest.raises(JobError, match="must be one of"):
        validate("design", {**AXES, "scale": "huge"}, role="user", live_enabled=False)


@pytest.mark.parametrize(
    "spec",
    [
        "../x",
        "C:\\x",
        "abcdef012345678",
        "ABCDEF0123456789",
        "abcdef01234567890",
        "abcdef0123456789\n",
        "",
        None,
        5,
    ],
)
def test_a_plan_job_refuses_anything_but_a_run_id(spec: Any) -> None:
    with pytest.raises(JobError, match="16 character lowercase hex"):
        validate("plan", {"spec": spec}, role="user", live_enabled=False)


def test_the_terraform_backend_is_admin_only_but_local_is_open() -> None:
    ok, live = validate("plan", {"spec": "a" * 16}, role="user", live_enabled=False)
    assert ok["backend"] == "local" and live is False
    with pytest.raises(JobError, match="admin only"):
        validate(
            "plan", {"spec": "a" * 16, "backend": "terraform"}, role="user", live_enabled=False
        )
    admin, live = validate(
        "plan", {"spec": "a" * 16, "backend": "terraform"}, role="admin", live_enabled=False
    )
    assert admin["backend"] == "terraform" and live is False  # an offline plan spends nothing


def test_a_real_apply_needs_an_admin_and_live_mode() -> None:
    raw = {"plan": "b" * 16, "backend": "terraform", "confirm": "b" * 16, "budgets_applied": True}
    with pytest.raises(JobError, match="admin only"):
        validate("apply", raw, role="user", live_enabled=True)
    with pytest.raises(JobError, match="switched off"):
        validate("apply", raw, role="admin", live_enabled=False)
    params, live = validate("apply", raw, role="admin", live_enabled=True)
    assert live is True and params["confirm"] == "b" * 16


def test_a_local_apply_is_open_to_a_user_and_stays_replay() -> None:
    params, live = validate("apply", {"plan": "c" * 16}, role="user", live_enabled=False)
    assert params["backend"] == "local" and params["confirm"] == "" and live is False
    for bad in ("../x", "C" * 16, "c" * 15):
        with pytest.raises(JobError):
            validate("apply", {"plan": bad}, role="user", live_enabled=False)
        with pytest.raises(JobError):
            validate("apply", {"plan": "c" * 16, "confirm": bad}, role="user", live_enabled=False)


def test_only_a_terraform_apply_counts_as_reaching_a_cloud() -> None:
    assert is_cloud("apply", {"backend": "terraform"}) is True
    assert is_cloud("apply", {"backend": "local"}) is False
    assert is_cloud("plan", {"backend": "terraform"}) is False
    assert is_cloud("review", {"s3_bucket": "my-bucket"}) is True


# --- the child environment -----------------------------------------------------------


def test_only_a_real_apply_child_is_switched_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KGCR_APPLY_ENABLED", "1")  # a server started with it set must not leak it
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    runner = Runner(Database(tmp_path / "d.sqlite3"), tmp_path)
    assert runner.child_env(live=False)["KGCR_APPLY_ENABLED"] == "0"
    assert runner.child_env(live=True, cloud=True)["KGCR_APPLY_ENABLED"] == "0"
    real = runner.child_env(live=False, cloud=True, apply_real=True)
    assert real["KGCR_APPLY_ENABLED"] == "1" and real["AWS_SECRET_ACCESS_KEY"] == "secret"


def test_the_run_is_found_in_plan_and_apply_logs() -> None:
    plan_log = "plan 0019fa7c9cabc8cd  run 9b94a79226bb63a3  backend local  baseline empty\n"
    apply_log = (
        "apply of plan 0019fa7c9cabc8cd: applied (local, simulated)\n  run 9b94a79226bb63a3\n"
    )
    assert _run_prefix(plan_log) == "9b94a79226bb63a3"
    assert _run_prefix(apply_log) == "9b94a79226bb63a3"
    assert _run_prefix("the word run alone") is None


# --- HTTP ----------------------------------------------------------------------------


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    server = make_server(0, tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", tmp_path
    server.shutdown()
    server.server_close()


def _session(base: str, role: str = "user") -> str:
    _, body = call(f"{base}/api/sessions", {"role": role}, DASH)
    return str(body["id"])


def test_meta_offers_the_axes_and_the_open_choices(served: tuple[str, Path]) -> None:
    base, _ = served
    _, meta = call(f"{base}/api/meta")
    assert meta["design_axes"]["scale"] == ["small", "medium", "large"]
    assert meta["planned"] == []
    backend = meta["jobs"]["plan"]["params"]["backend"]
    assert backend["choices"] == ["local", "terraform"] and backend["admin_values"] == ["terraform"]
    assert meta["jobs"]["design"]["params"]["archetype"]["default"] is None


def test_a_runs_plans_are_listed_with_their_lifecycle(served: tuple[str, Path]) -> None:
    base, root = served
    prefix = _run(root, mode="design")
    plan = make_plan(root, prefix)
    status, body = call(f"{base}/api/runs/{prefix}/plans")
    assert status == 200 and body["mode"] == "design"
    assert [p["plan"]["plan_id"] for p in body["plans"]] == [plan["plan_id"]]
    assert [e["event"] for e in body["events"]] == ["planned"]
    status, one = call(f"{base}/api/plans/{plan['plan_id']}")
    assert status == 200 and one["plan"]["creates"] and one["apply"] is None


@pytest.mark.parametrize("bad", ["zzzz", "..%2f..", "ABCDEF0123456789", "ffffffffffffffff"])
def test_hostile_or_unknown_ids_are_not_found(served: tuple[str, Path], bad: str) -> None:
    base, _ = served
    assert call(f"{base}/api/runs/{bad}/plans")[0] == 404
    assert call(f"{base}/api/plans/{bad}")[0] == 404


def test_extraction_needs_a_session_and_a_sane_statement(served: tuple[str, Path]) -> None:
    base, _ = served
    assert call(f"{base}/api/design/extract", {"statement": "x"}, DASH)[0] == 401
    sid = _session(base)
    assert call(f"{base}/api/design/extract", {"session": sid, "statement": 5}, DASH)[0] == 400
    status, body = call(
        f"{base}/api/design/extract", {"session": sid, "statement": "x" * 2001}, DASH
    )
    assert status == 400 and "limit" in body["error"]


def test_extraction_replays_a_recorded_statement_without_a_model(served: tuple[str, Path]) -> None:
    base, _ = served
    status, body = call(
        f"{base}/api/design/extract", {"session": _session(base), "statement": STATEMENT}, DASH
    )
    assert status == 200 and body["live"] is False and body["llm_status"] == "ok"
    assert body["fields"]["archetype"]["value"] == "payments_api"
    assert body["fields"]["archetype"]["evidence"] == "payments API"


def test_an_unrecorded_statement_in_replay_is_all_null_not_a_model_call(
    served: tuple[str, Path],
) -> None:
    base, _ = served
    status, body = call(
        f"{base}/api/design/extract",
        {"session": _session(base), "statement": "A statement nobody recorded."},
        DASH,
    )
    assert status == 200 and body["llm_status"] == "missing_fixture" and body["live"] is False
    assert all(f["value"] is None for f in body["fields"].values())


def test_a_user_cannot_spend_even_when_an_admin_switched_live_on(
    served: tuple[str, Path],
) -> None:
    base, _ = served
    admin = _session(base, "admin")
    call(f"{base}/api/admin/live", {"session": admin, "enabled": True, "confirm": True}, DASH)
    status, body = call(
        f"{base}/api/design/extract",
        {"session": _session(base), "statement": "Another statement nobody recorded."},
        DASH,
    )
    assert status == 200 and body["live"] is False and body["llm_status"] == "missing_fixture"


def test_intent_fixtures_are_listed_and_readable(served: tuple[str, Path]) -> None:
    base, _ = served
    _, rows = call(f"{base}/api/fixtures")
    intent = [r for r in rows if r["label"].startswith("intent-v1-")]
    assert intent and all(r["kind"] == "intent extraction" for r in intent)
    status, fixture = call(f"{base}/api/fixtures/{intent[0]['label']}")
    assert status == 200 and "response" in fixture


def test_the_cloud_page_reports_the_gates_without_leaking_identifiers(
    served: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    base, _ = served
    monkeypatch.setenv("KGCR_PROVISION_ROLE_ARN", "arn:aws:iam::123456789012:role/SENTINEL")
    monkeypatch.setenv("KGCR_APPLY_ACCOUNT_ID", "123456789012")
    _, cloud = call(f"{base}/api/cloud")
    assert cloud["apply"] == {
        "role_configured": True,
        "account_configured": True,
        "granted_services": ["ec2", "s3"],
    }
    assert "SENTINEL" not in json.dumps(cloud) and "123456789012" not in json.dumps(cloud)
    assert isinstance(cloud["terraform_installed"], bool)
