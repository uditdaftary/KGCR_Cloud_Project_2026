"""The controls review and the gold register: human acts only, append-only, frozen on
sign-off, and never touching the controls the advisor reads."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from kgcr.advisor.controls import DRAFT_CONTROLS_PATH
from kgcr.corpus.generator import render_estate
from kgcr.corpus.sampler import IntentSampler
from kgcr.dashboard import authoring
from kgcr.dashboard.authoring import AuthoringError
from kgcr.dashboard.db import Database
from kgcr.dashboard.server import make_server
from kgcr.orchestration.common import graph_version
from tests.dashboard.test_dashboard_api import DASH, call

SRC = Path(__file__).resolve().parents[2] / "src" / "backend" / "kgcr" / "dashboard"
NODE = "kg://control/pci-dss-v4/3.5.1"
FRAMEWORK = "AWS Well-Architected Framework"


def _config(encrypted: bool = True) -> str:
    # A plainly labelled test fixture, not gold data.
    doc = render_estate(IntentSampler(3).sample(), 3).to_terraform_json()
    for body in doc["resource"].get("aws_db_instance", {}).values():
        body["storage_encrypted"] = encrypted
    return json.dumps(doc)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "d.sqlite3")


# --- controls review -----------------------------------------------------------------


def test_decisions_append_and_the_latest_wins(db: Database) -> None:
    authoring.record_decision(
        db, NODE, "needs_change", "Reviewer A", "wording", "A better summary."
    )
    authoring.record_decision(db, NODE, "verified", "Reviewer A", "checked against PCI-DSS 3.5.1")
    view = authoring.controls_view(db)
    control = next(c for c in view["controls"] if c["control_node"] == NODE)
    assert control["decisions"] == 2 and control["latest"]["decision"] == "verified"
    export = authoring.controls_export(db)
    row = next(c for c in export["controls"] if c["control_node"] == NODE)
    assert [h["decision"] for h in row["history"]] == ["needs_change", "verified"]
    assert row["current_decision"] == "verified"


def test_recording_a_decision_never_touches_what_the_advisor_reads(db: Database) -> None:
    before = (DRAFT_CONTROLS_PATH.read_bytes(), graph_version())
    authoring.record_decision(db, NODE, "verified", "Reviewer A")
    assert (DRAFT_CONTROLS_PATH.read_bytes(), graph_version()) == before
    export = authoring.controls_export(db)
    assert "does not change the controls the advisor reads" in export["statement"]
    assert all(c["verified_in_draft"] is False for c in export["controls"])  # still the draft's


def test_the_review_table_has_no_update_or_delete_path() -> None:
    for name in ("authoring.py", "db.py"):
        text = (SRC / name).read_text(encoding="utf-8").upper()
        assert "UPDATE CONTROL_REVIEWS" not in text and "DELETE FROM CONTROL_REVIEWS" not in text


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"control_node": "kg://control/made-up"}, "not a control"),
        ({"decision": "approved"}, "decision must be one of"),
        ({"reviewer": ""}, "reviewer is required"),
        ({"reviewer": "x" * 81}, "longer than"),
        ({"note": "x" * 2001}, "longer than"),
        ({"decision": "verified", "proposed_summary": "text"}, "belongs only with"),
        ({"decision": "needs_change"}, "say what needs to change"),
    ],
)
def test_a_malformed_decision_is_refused_and_writes_nothing(
    db: Database, kwargs: dict[str, Any], message: str
) -> None:
    args: dict[str, Any] = {"control_node": NODE, "decision": "verified", "reviewer": "Reviewer A"}
    with pytest.raises(AuthoringError, match=message):
        authoring.record_decision(db, **{**args, **kwargs})
    assert authoring.controls_export(db)["controls"][0]["history"] == []


# --- gold set register ---------------------------------------------------------------


def _entry(db: Database, **over: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "title": "Encrypted data store, multi-AZ",
        "framework": FRAMEWORK,
        "source_ref": "Reliability pillar, data stores (hand transcribed)",
        "config": _config(),
        "controls": [NODE],
        "author": "Author One",
    }
    return authoring.gold_create(db, **{**fields, **over})


def test_an_entry_goes_draft_authored_reviewed_and_is_then_frozen(db: Database) -> None:
    entry = _entry(db)
    assert entry["status"] == "draft"
    authored = authoring.gold_mark_authored(db, entry["id"])
    assert authored["status"] == "authored"
    signed = authoring.gold_review(db, entry["id"], "Instructor", "Reads as compliant.")
    assert signed["status"] == "reviewed" and signed["review_check"]["criticals"] == []
    with pytest.raises(AuthoringError, match="frozen"):
        authoring.gold_update(db, entry["id"], title="Changed")
    assert authoring.gold_list(db)["reviewed"] == 1


def test_an_edit_takes_an_authored_entry_back_to_draft(db: Database) -> None:
    entry = _entry(db)
    authoring.gold_mark_authored(db, entry["id"])
    edited = authoring.gold_update(db, entry["id"], title="Reworded")
    assert edited["status"] == "draft" and edited["title"] == "Reworded"


def test_the_reviewer_must_be_someone_else_and_the_entry_authored(db: Database) -> None:
    entry = _entry(db)
    with pytest.raises(AuthoringError, match="only an authored entry"):
        authoring.gold_review(db, entry["id"], "Instructor")
    authoring.gold_mark_authored(db, entry["id"])
    with pytest.raises(AuthoringError, match="someone other than the author"):
        authoring.gold_review(db, entry["id"], "  author one ")


def test_a_configuration_the_rules_flag_critical_cannot_be_signed_off(db: Database) -> None:
    entry = _entry(db, config=_config(encrypted=False))
    if not authoring.gold_check(db, entry["id"])["criticals"]:
        pytest.skip("the sampled estate has no database to flag")
    authoring.gold_mark_authored(db, entry["id"])
    with pytest.raises(AuthoringError, match="CRITICAL"):
        authoring.gold_review(db, entry["id"], "Instructor")


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"framework": "A blog post"}, "framework must be one of"),
        ({"config": "not json"}, "not JSON"),
        ({"config": json.dumps({"resource": {}})}, "no resources"),
        ({"config": json.dumps({"provider": {}})}, "'resource' block"),
        ({"config": "x" * 200_001}, "longer than"),
        ({"controls": ["kg://control/made-up"]}, "not controls"),
        ({"controls": "all"}, "list of control ids"),
        ({"title": ""}, "title is required"),
        ({"author": ""}, "author is required"),
    ],
)
def test_a_malformed_entry_is_refused(db: Database, over: dict[str, Any], message: str) -> None:
    with pytest.raises(AuthoringError, match=message):
        _entry(db, **over)
    assert authoring.gold_list(db)["entries"] == []


def test_an_entry_must_name_its_controls_before_it_is_authored(db: Database) -> None:
    entry = _entry(db, controls=[])
    with pytest.raises(AuthoringError, match="name the controls"):
        authoring.gold_mark_authored(db, entry["id"])


def test_the_export_carries_the_target_and_never_the_corpus(db: Database) -> None:
    _entry(db)
    export = authoring.gold_export(db)
    assert export["target"] == 50 and len(export["entries"]) == 1
    assert "never trained on" in export["statement"]


def test_progress_counts_authored_and_reviewed(db: Database) -> None:
    a, b = _entry(db), _entry(db, title="Second")
    authoring.gold_mark_authored(db, a["id"])
    authoring.gold_mark_authored(db, b["id"])
    authoring.gold_review(db, a["id"], "Instructor")
    listed = authoring.gold_list(db)
    assert (listed["authored"], listed["reviewed"], listed["target"]) == (2, 1, 50)


# --- HTTP ----------------------------------------------------------------------------


@pytest.fixture
def served(tmp_path: Path) -> Iterator[str]:
    server = make_server(0, tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _sid(base: str, role: str) -> str:
    return str(call(f"{base}/api/sessions", {"role": role}, DASH)[1]["id"])


def test_only_an_admin_who_confirms_can_record_a_decision(served: str) -> None:
    body = {"control_node": NODE, "decision": "verified", "reviewer": "Reviewer A"}
    user, admin = _sid(served, "user"), _sid(served, "admin")
    url = f"{served}/api/authoring/controls/decision"
    assert call(url, {**body, "session": user, "confirm": True}, DASH)[0] == 403
    status, err = call(url, {**body, "session": admin}, DASH)
    assert status == 400 and "confirm" in err["error"]
    status, ok = call(url, {**body, "session": admin, "confirm": True}, DASH)
    assert status == 201 and ok["decision"] == "verified"
    _, view = call(f"{served}/api/authoring/controls")
    assert next(c for c in view["controls"] if c["control_node"] == NODE)["decisions"] == 1


def test_exports_download_as_files(served: str) -> None:
    for path, name in (
        ("authoring/controls/export", "controls_review.json"),
        ("gold/export", "gold_set.json"),
    ):
        with urllib.request.urlopen(f"{served}/api/{path}", timeout=30) as res:
            assert f'filename="{name}"' in res.headers["Content-Disposition"]
            assert "attachment" in res.headers["Content-Disposition"]
            assert json.loads(res.read())["kind"] in ("controls_review", "gold_set")


def test_the_gold_register_over_http(served: str) -> None:
    admin = _sid(served, "admin")
    body = {
        "session": admin,
        "title": "Entry",
        "framework": FRAMEWORK,
        "source_ref": "a source",
        "config": _config(),
        "controls": [NODE],
        "author": "Author One",
    }
    status, entry = call(f"{served}/api/gold", body, DASH)
    assert status == 201 and entry["status"] == "draft"
    eid = entry["id"]
    status, checked = call(f"{served}/api/gold/{eid}/check", {"session": admin}, DASH)
    assert status == 200 and checked["criticals"] == []
    assert call(f"{served}/api/gold/{eid}/authored", {"session": admin}, DASH)[0] == 200
    review = {"session": admin, "reviewer": "Author One", "confirm": True}
    status, err = call(f"{served}/api/gold/{eid}/review", review, DASH)
    assert status == 400 and "someone other" in err["error"]
    status, err = call(
        f"{served}/api/gold/{eid}/review",
        {**review, "reviewer": "Instructor", "confirm": None},
        DASH,
    )
    assert status == 400 and "confirm" in err["error"]
    status, signed = call(
        f"{served}/api/gold/{eid}/review", {**review, "reviewer": "Instructor"}, DASH
    )
    assert status == 200 and signed["status"] == "reviewed"
    status, err = call(f"{served}/api/gold/{eid}", {"session": admin, "title": "x"}, DASH)
    assert status == 400 and "frozen" in err["error"]
    _, listed = call(f"{served}/api/gold")
    assert listed["reviewed"] == 1 and "config" not in listed["entries"][0]
    assert call(f"{served}/api/gold/{eid}")[1]["config"]["resource"]
    assert call(f"{served}/api/gold/999")[0] == 404


def test_a_user_session_cannot_write_to_the_register(served: str) -> None:
    user = _sid(served, "user")
    status, _ = call(f"{served}/api/gold", {"session": user, "title": "x"}, DASH)
    assert status == 403


def test_an_unknown_authoring_route_is_not_found(served: str) -> None:
    admin = _sid(served, "admin")
    assert call(f"{served}/api/authoring/nothing", {"session": admin}, DASH)[0] == 404
    try:
        call(f"{served}/api/gold/abc/check", {"session": admin}, DASH)
    except urllib.error.HTTPError as err:  # pragma: no cover - call() already maps errors
        assert err.code == 404
