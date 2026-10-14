"""Human-authored review records: the controls review and the gold set register.

FD-07 section 2: L1 is authored, not learned. **A model may read L1 but never write it.**
Nothing here is ever called with data a model produced; every write needs an admin session,
a typed reviewer name and an explicit confirmation, and the routes refuse otherwise.

* ``control_reviews`` is append-only. Recording a decision never touches the draft controls
  file the advisor reads, so it cannot change a prompt, a fixture hash or a graph version.
  Promoting reviewed controls into that file is a separate, deliberate step that makes a
  new graph version (FD-07 section 10) and, if any summary changes, invalidates the recorded
  fixtures.
* The gold set is 50 to 100 hand-authored, compliant-by-construction configurations, never
  drawn from the synthetic corpus and never trained on (FD-05 4C).
* Both are exported as downloads: the dashboard never writes into ``results/``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from kgcr.advisor.controls import DRAFT_CONTROLS_PATH
from kgcr.dashboard.db import Database
from kgcr.gold.check import check_config

__all__ = [
    "AuthoringError",
    "DECISIONS",
    "FRAMEWORKS",
    "GOLD_TARGET",
    "controls_export",
    "controls_view",
    "gold_check",
    "gold_create",
    "gold_export",
    "gold_get",
    "gold_list",
    "gold_mark_authored",
    "gold_review",
    "gold_update",
    "record_decision",
]

DECISIONS = ("verified", "needs_change", "rejected")
FRAMEWORKS = (
    "AWS Well-Architected Framework",
    "AWS Security Reference Architecture",
    "Financial-services reference architecture",
    "Other published reference",
)
GOLD_TARGET = 50  # FD-05 4C asks for 50 to 100
MAX_NAME, MAX_NOTE, MAX_SUMMARY, MAX_CONFIG, MAX_TITLE = 80, 2000, 1000, 200_000, 160


class AuthoringError(ValueError):
    """A request the authoring tools refuse; the message is shown to the operator."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any, field: str, limit: int, *, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise AuthoringError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise AuthoringError(f"{field} is required")
    if len(value) > limit:
        raise AuthoringError(f"{field} is longer than {limit} characters")
    return value


def _draft() -> dict[str, Any]:
    draft: dict[str, Any] = json.loads(DRAFT_CONTROLS_PATH.read_text(encoding="utf-8"))
    return draft


def _control_nodes() -> set[str]:
    return {c["control_node"] for c in _draft()["controls"]}


# --- controls review -----------------------------------------------------------------


def _decisions(db: Database) -> list[dict[str, Any]]:
    with db.connection() as c:
        rows = c.execute("SELECT * FROM control_reviews ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def controls_view(db: Database) -> dict[str, Any]:
    """The draft controls with each one's latest human decision and how many there have been."""
    draft = _draft()
    by_control: dict[str, list[dict[str, Any]]] = {}
    for row in _decisions(db):
        by_control.setdefault(row["control_node"], []).append(row)
    controls = []
    for control in draft["controls"]:
        rows = by_control.get(control["control_node"], [])
        controls.append({**control, "latest": rows[-1] if rows else None, "decisions": len(rows)})
    return {
        "status": draft["status"],
        "note": draft["note"],
        "classification_to_severity": draft["classification_to_severity"],
        "draft_sha256": hashlib.sha256(DRAFT_CONTROLS_PATH.read_bytes()).hexdigest(),
        "controls": controls,
    }


def record_decision(
    db: Database,
    control_node: Any,
    decision: Any,
    reviewer: Any,
    note: Any = "",
    proposed_summary: Any = None,
) -> dict[str, Any]:
    """Append one human decision about one control. Never edits the draft controls file."""
    if control_node not in _control_nodes():
        raise AuthoringError("not a control in the draft slice")
    if decision not in DECISIONS:
        raise AuthoringError(f"decision must be one of: {', '.join(DECISIONS)}")
    reviewer = _text(reviewer, "reviewer", MAX_NAME)
    note = _text(note, "note", MAX_NOTE, required=False)
    proposed = _text(proposed_summary, "proposed summary", MAX_SUMMARY, required=False)
    if proposed and decision != "needs_change":
        raise AuthoringError("a proposed summary belongs only with 'needs change'")
    if decision == "needs_change" and not (proposed or note):
        raise AuthoringError("say what needs to change: a proposed summary or a note")
    created = _now()
    with db.connection() as c:
        c.execute(
            "INSERT INTO control_reviews "
            "(control_node, decision, proposed_summary, note, reviewer, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (control_node, decision, proposed or None, note, reviewer, created),
        )
    return {"control_node": control_node, "decision": decision, "reviewer": reviewer, "at": created}


def controls_export(db: Database) -> dict[str, Any]:
    """A file of decisions for the reviewer to commit. It does not change any control."""
    view = controls_view(db)
    history: dict[str, list[dict[str, Any]]] = {}
    for row in _decisions(db):
        history.setdefault(row["control_node"], []).append(
            {k: row[k] for k in ("decision", "proposed_summary", "note", "reviewer", "created_at")}
        )
    return {
        "exported_at": _now(),
        "kind": "controls_review",
        "statement": (
            "Decisions recorded by a human reviewer about the draft L1 controls. This file does "
            "not change the controls the advisor reads; promoting reviewed controls is a "
            "separate step that makes a new graph version."
        ),
        "draft_file_sha256": view["draft_sha256"],
        "controls": [
            {
                "control_node": c["control_node"],
                "control_ref": c["control_ref"],
                "summary_in_draft": c["summary"],
                "verified_in_draft": c["verified"],
                "current_decision": c["latest"]["decision"] if c["latest"] else None,
                "history": history.get(c["control_node"], []),
            }
            for c in view["controls"]
        ],
    }


# --- gold set register ---------------------------------------------------------------


def _parse_config(raw: Any) -> dict[str, Any]:
    text = _text(raw, "configuration", MAX_CONFIG)
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise AuthoringError(f"the configuration is not JSON: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("resource"), dict):
        raise AuthoringError("the configuration must be Terraform JSON with a 'resource' block")
    try:
        check_config(doc)  # rejects malformed or empty documents
    except ValueError as exc:
        raise AuthoringError(str(exc)) from exc
    return doc


def _controls(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > 20 or not all(isinstance(x, str) for x in raw):
        raise AuthoringError("controls must be a list of control ids")
    known = _control_nodes()
    unknown = [x for x in raw if x not in known]
    if unknown:
        raise AuthoringError(f"not controls in the draft slice: {', '.join(unknown)}")
    return sorted(set(raw))


def _entry(row: Any, *, with_config: bool) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "title": row["title"],
        "framework": row["framework"],
        "source_ref": row["source_ref"],
        "controls": json.loads(row["controls_json"]),
        "author": row["author"],
        "status": row["status"],
        "reviewer": row["reviewer"],
        "review_note": row["review_note"],
        "review_check": json.loads(row["review_check_json"]) if row["review_check_json"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "reviewed_at": row["reviewed_at"],
    }
    if with_config:
        out["config"] = json.loads(row["config_json"])
    return out


def _row(db: Database, entry_id: Any) -> Any:
    if isinstance(entry_id, bool) or not isinstance(entry_id, int):
        raise AuthoringError("not a gold entry")
    with db.connection() as c:
        row = c.execute("SELECT * FROM gold_entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise AuthoringError("no such gold entry")
    return row


def gold_list(db: Database) -> dict[str, Any]:
    with db.connection() as c:
        rows = c.execute("SELECT * FROM gold_entries ORDER BY id").fetchall()
    entries = [_entry(r, with_config=False) for r in rows]
    return {
        "target": GOLD_TARGET,
        "frameworks": list(FRAMEWORKS),
        "authored": sum(e["status"] in ("authored", "reviewed") for e in entries),
        "reviewed": sum(e["status"] == "reviewed" for e in entries),
        "entries": entries,
    }


def gold_get(db: Database, entry_id: Any) -> dict[str, Any]:
    return _entry(_row(db, entry_id), with_config=True)


def gold_create(
    db: Database,
    *,
    title: Any,
    framework: Any,
    source_ref: Any,
    config: Any,
    controls: Any,
    author: Any,
) -> dict[str, Any]:
    if framework not in FRAMEWORKS:
        raise AuthoringError(f"framework must be one of: {'; '.join(FRAMEWORKS)}")
    doc = _parse_config(config)
    now = _now()
    with db.connection() as c:
        cur = c.execute(
            "INSERT INTO gold_entries (title, framework, source_ref, config_json, controls_json, "
            "author, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?)",
            (
                _text(title, "title", MAX_TITLE),
                framework,
                _text(source_ref, "source reference", MAX_SUMMARY),
                json.dumps(doc, sort_keys=True),
                json.dumps(_controls(controls)),
                _text(author, "author", MAX_NAME),
                now,
                now,
            ),
        )
    return gold_get(db, cur.lastrowid)


def gold_update(db: Database, entry_id: Any, **fields: Any) -> dict[str, Any]:
    """Edit a draft or authored entry. A reviewed entry is frozen: write a new one."""
    row = _row(db, entry_id)
    if row["status"] == "reviewed":
        raise AuthoringError("a reviewed entry is frozen; create a new entry instead")
    allowed = {"title", "framework", "source_ref", "config", "controls"}
    unknown = set(fields) - allowed
    if unknown:
        raise AuthoringError(f"cannot edit: {', '.join(sorted(unknown))}")
    values: dict[str, Any] = {}
    if "title" in fields:
        values["title"] = _text(fields["title"], "title", MAX_TITLE)
    if "framework" in fields:
        if fields["framework"] not in FRAMEWORKS:
            raise AuthoringError(f"framework must be one of: {'; '.join(FRAMEWORKS)}")
        values["framework"] = fields["framework"]
    if "source_ref" in fields:
        values["source_ref"] = _text(fields["source_ref"], "source reference", MAX_SUMMARY)
    if "config" in fields:
        values["config_json"] = json.dumps(_parse_config(fields["config"]), sort_keys=True)
    if "controls" in fields:
        values["controls_json"] = json.dumps(_controls(fields["controls"]))
    if not values:
        return gold_get(db, entry_id)
    # An edit takes an authored entry back to draft: it must be marked authored again.
    values["status"] = "draft"
    values["updated_at"] = _now()
    assignments = ", ".join(f"{column} = ?" for column in values)  # fixed column names above
    with db.connection() as c:
        c.execute(
            f"UPDATE gold_entries SET {assignments} WHERE id = ?", (*values.values(), entry_id)
        )  # noqa: S608
    return gold_get(db, entry_id)


def gold_mark_authored(db: Database, entry_id: Any) -> dict[str, Any]:
    row = _row(db, entry_id)
    if row["status"] != "draft":
        raise AuthoringError(f"only a draft can be marked authored (this one is {row['status']})")
    if not json.loads(row["controls_json"]):
        raise AuthoringError("name the controls this configuration exercises first")
    with db.connection() as c:
        c.execute(
            "UPDATE gold_entries SET status = 'authored', updated_at = ? WHERE id = ?",
            (_now(), entry_id),
        )
    return gold_get(db, entry_id)


def gold_check(db: Database, entry_id: Any) -> dict[str, Any]:
    """Run the rule floor over an entry: the FD-07 acceptance check, computed on demand."""
    return check_config(gold_get(db, entry_id)["config"]).to_dict()


def gold_review(db: Database, entry_id: Any, reviewer: Any, note: Any = "") -> dict[str, Any]:
    """Instructor sign-off. Freezes the entry; refused on the author, or on any CRITICAL."""
    row = _row(db, entry_id)
    reviewer = _text(reviewer, "reviewer", MAX_NAME)
    if row["status"] != "authored":
        raise AuthoringError(
            f"only an authored entry can be signed off (this one is {row['status']})"
        )
    if reviewer.casefold() == row["author"].casefold():
        raise AuthoringError("the reviewer must be someone other than the author")
    check = check_config(json.loads(row["config_json"]))
    if check.criticals:
        raise AuthoringError(
            f"the rule floor raises {len(check.criticals)} CRITICAL finding(s): either the "
            "configuration or the L1 encoding is wrong, so it cannot be signed off as compliant"
        )
    now = _now()
    with db.connection() as c:
        c.execute(
            "UPDATE gold_entries SET status = 'reviewed', reviewer = ?, review_note = ?, "
            "review_check_json = ?, reviewed_at = ?, updated_at = ? WHERE id = ?",
            (
                reviewer,
                _text(note, "note", MAX_NOTE, required=False),
                json.dumps(check.to_dict(), sort_keys=True),
                now,
                now,
                entry_id,
            ),
        )
    return gold_get(db, entry_id)


def gold_export(db: Database) -> dict[str, Any]:
    with db.connection() as c:
        rows = c.execute("SELECT * FROM gold_entries ORDER BY id").fetchall()
    return {
        "exported_at": _now(),
        "kind": "gold_set",
        "statement": (
            "Hand-authored reference configurations, compliant by construction. Evaluation "
            "only: never trained on, at any stage (FD-05 4C)."
        ),
        "target": GOLD_TARGET,
        "entries": [_entry(r, with_config=True) for r in rows],
    }
