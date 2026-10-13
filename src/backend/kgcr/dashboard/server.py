"""``kgcr dashboard``: a stdlib HTTP server for the single-page dashboard and its JSON API.

Bound to 127.0.0.1 with no login, by decision: the operator picks user or admin on
the cover. Two cheap guards still apply because any web page open in the same
browser can reach localhost: the Host header must name this server (DNS
rebinding), and every POST must be JSON carrying the ``X-KGCR`` header, which a
cross-site form cannot send without a CORS preflight this server never grants.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import logging
import mimetypes
import os
import re
import subprocess
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from kgcr._version import __version__
from kgcr.dashboard.db import Database
from kgcr.dashboard.jobs import FIXTURES, JOB_KINDS, ROOT, JobError, Runner, validate
from kgcr.repro import DEFAULT_COUNT, DEFAULT_SEED

__all__ = ["make_server", "serve"]

logger = logging.getLogger(__name__)

FRONTEND = ROOT / "src" / "frontend"
RESULTS = ROOT / "results"
# Read-only project files the dashboard may show, by directory and extension.
REPO_FILES = {"architecture": {".png", ".svg"}, "docs": {".md"}, "dataset": {".md"}}
MAX_BODY = 64 * 1024
_FIXTURE_LABEL = re.compile(r"^(intent-)?v1(-[a-z0-9]{1,32}){1,4}$")
_VARIANT_NAMES = {
    "cloudtrail_no_log_validation": "CloudTrail without log validation",
    "wildcard_iam_policy": "Wildcard IAM policy",
    "privilege_escalation_passrole": "PassRole privilege escalation",
}


class App:
    """Shared state behind every request: the database, the job runner, the live switch."""

    def __init__(self, store_root: Path) -> None:
        self.store_root = store_root
        self.db = Database(store_root / "dashboard.sqlite3")
        self.live_enabled = False  # in memory on purpose: every restart is back to replay
        self.runner = Runner(self.db, store_root, live_allowed=lambda: self.live_enabled)
        self._lock = threading.Lock()

    def set_live(self, enabled: bool) -> None:
        with self._lock:
            self.live_enabled = enabled


# --- read models ---------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


@functools.lru_cache(maxsize=4)
def variant_roster(count: int, seed: int) -> list[dict[str, Any]]:
    """The nine injectable variants, and whether recorded model responses cover each one.

    Replay works only for the estate the fixtures were recorded on, so this regenerates
    the held-out target per variant at ``(count, seed)`` and looks for its loop fixture.
    """
    from kgcr.corpus.graph import build_graph_from_estate
    from kgcr.corpus.pipeline import generate_corpus
    from kgcr.corpus.splits import split_estates
    from kgcr.defects.inject import INJECTORS
    from kgcr.defects.taxonomy import DEFAULT_SEVERITY, DETECTABILITY
    from kgcr.orchestration.review import select_target

    corpus = generate_corpus(count, seed)
    by_id = {e.estate_id: e for e in corpus}
    test = [by_id[i] for i in split_estates(corpus).test.estate_ids]
    rows = []
    for inj in INJECTORS:
        estate_id: str | None = None
        graph: dict[str, Any] | None = None
        seeded: list[str] = []
        try:
            target = select_target(test, inj.variant)
        except ValueError as exc:  # expected: no held-out estate admits some variants
            logger.info("roster: no estate for %s (%s)", inj.variant, exc)
            target = None
        if target is not None:
            estate_id = target.estate.estate_id
            g = build_graph_from_estate(target.estate)
            graph = {
                "nodes": [{"address": n.address, "type": n.type} for n in g.nodes],
                "edges": [[e.source, e.target] for e in g.edges],
            }
            seeded = list(target.defect.evidence_path or target.defect.injection_site)
        fixture = estate_id is not None and any(FIXTURES.glob(f"v1-{estate_id}-loop-p*.json"))
        rows.append(
            {
                "variant": inj.variant,
                "name": _VARIANT_NAMES.get(inj.variant, inj.variant.replace("_", " ").capitalize()),
                "defect_class": inj.defect_class.value,
                "severity": DEFAULT_SEVERITY[inj.defect_class].value,
                "detectability": DETECTABILITY[inj.defect_class].value,
                "estate_id": estate_id,
                "graph": graph,
                "seeded": seeded,
                "replay": bool(fixture),
            }
        )
    return rows


def meta(app: App) -> dict[str, Any]:
    from kgcr.advisor.llm import GEMINI_MODEL, LIVE_CALL_CAP
    from kgcr.design.intake import axis_choices
    from kgcr.explainer.explainer import AUDIENCES

    return {
        "version": __version__,
        "audiences": list(AUDIENCES),
        "design_axes": {axis: list(values) for axis, values in axis_choices().items()},
        "default_seed": DEFAULT_SEED,
        "default_count": DEFAULT_COUNT,
        "live_enabled": app.live_enabled,
        "live_call_cap": LIVE_CALL_CAP,
        "gemini_model": GEMINI_MODEL,
        "gemini_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "deferred": DEFERRED,
        "jobs": {
            k: {
                "label": s.label,
                "summary": s.summary,
                "writes": s.writes,
                "admin_only": s.admin_only,
                "can_go_live": s.can_go_live,
                "params": {
                    n: {
                        "kind": p.kind,
                        "default": p.default,
                        "low": p.low,
                        "high": p.high,
                        "choices": list(p.choices),
                        "admin_only": p.admin_only,
                        "admin_values": list(p.admin_values),
                        "label": p.label or n,
                    }
                    for n, p in s.params.items()
                },
            }
            for k, s in JOB_KINDS.items()
        },
    }


def job_view(app: App, job_id: int) -> dict[str, Any] | None:
    job = app.db.job(job_id)
    if job is None:
        return None
    live = app.runner.live_log(job_id)
    if live is not None:
        job["log"] = live
    job["queue_position"] = app.runner.position(job_id)
    outputs: dict[str, Any] = {}
    # Only once finished: a running job may be mid-write, and nothing needs them earlier.
    if job.get("output_dir") and job["status"] in ("done", "failed", "cancelled"):
        for path in sorted(Path(job["output_dir"]).glob("*.json")):
            try:
                if path.stat().st_size < 1_000_000:
                    outputs[path.name] = _read_json(path)
            except (OSError, ValueError) as exc:
                logger.warning("job %s output %s unreadable: %s", job_id, path.name, exc)
    job["outputs"] = outputs
    return job


def environment(app: App) -> dict[str, Any]:
    """What a job's child process reports for seeding and tool versions, read from a real one.

    Asked of a short-lived ``kgcr repro-info`` run with the environment jobs get, so the page
    matches the run records and this server process is never reseeded (nor imports torch).
    """
    report: dict[str, Any] = {}
    error = None
    try:
        done = subprocess.run(
            [sys.executable, "-m", "kgcr.cli", "repro-info", "--json"],
            cwd=ROOT,
            env=app.runner.child_env(live=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=True,
        )
        report = json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.exception("repro-info child failed")
        error = f"could not read the report from a child process: {exc}"
    return {
        "seed_report": report.get("seed_report", {}),
        "tool_versions": report.get("tool_versions", {}),
        "error": error,
        "dotenv_present": (ROOT / ".env").is_file(),
        "gemini_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "llm_live_in_env": os.environ.get("KGCR_LLM_LIVE") == "1",
    }


def cloud(app: App) -> dict[str, Any]:
    resources = []
    for tf in sorted((ROOT / "src" / "aws").glob("*.tf")):
        for kind, name in re.findall(
            r'^resource\s+"([^"]+)"\s+"([^"]+)"', tf.read_text("utf-8"), re.M
        ):
            resources.append({"file": tf.name, "type": kind, "name": name})
    from kgcr.apply.preflight import allowed_services
    from kgcr.plan.terraform_backend import terraform_binary

    binary = terraform_binary()
    version = None
    if binary:
        try:
            done = subprocess.run(
                [binary, "version", "-json"],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            version = json.loads(done.stdout).get("terraform_version")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            logger.warning("terraform version failed: %s", exc)
    return {
        "terraform_files": sorted(p.name for p in (ROOT / "src" / "aws").glob("*.tf")),
        "resources": resources,
        "terraform_installed": binary is not None,
        "terraform_version": version,
        "boto3_installed": importlib.util.find_spec("boto3") is not None,
        "live_enabled": app.live_enabled,
        "deployed": False,
        # What a real apply would check, from the server's environment. Names and counts only:
        # no account id, role or key is ever sent to the page.
        "apply": {
            "role_configured": bool(os.environ.get("KGCR_PROVISION_ROLE_ARN")),
            "account_configured": bool(os.environ.get("KGCR_APPLY_ACCOUNT_ID")),
            "granted_services": list(allowed_services(os.environ)),
        },
    }


def fixtures() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(FIXTURES.glob("*.json")):
        data = _read_json(path)
        kind = path.stem.split("-")[1]
        if path.stem.startswith("intent-"):
            kind_label = "intent extraction"
        else:
            kind_label = {"syc": "sycophancy trial", "clean": "clean estate"}.get(
                kind, "review loop"
            )
        rows.append(
            {
                "label": path.stem,
                "kind": kind_label,
                "model": data.get("model"),
                "prompt_sha256": data.get("prompt_sha256"),
                "response_chars": len(data.get("response", "")),
            }
        )
    return rows


def project() -> dict[str, Any]:
    """Deliverables as the README's Phase-I table lists them, plus the diagrams."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Phase-I deliverables", 1)[-1].split("\n## ", 1)[0]
    rows = re.findall(r"^\|\s*([^|]+?)\s*\|\s*\[[^\]]+\]\(([^)]+)\)\s*\|", section, re.M)
    return {
        "deliverables": [{"title": t, "path": p} for t, p in rows if not t.startswith("-")],
        "diagrams": [
            "architecture/AWS_Architecture.png",
            "architecture/System_Architecture.png",
        ],
    }


def preflight(plan: dict[str, Any]) -> dict[str, Any] | None:
    """Does the write role's grant cover a Terraform plan? None for any other plan.

    Computed here, from the same module the CLI uses, so the page never carries its own copy
    of the service mapping.
    """
    from kgcr.apply import preflight as grant

    section = plan.get("terraform")
    if not section:
        return None
    granted = grant.allowed_services(os.environ)
    types = {address.split(".", 1)[0] for address in section["creates"]}
    return {"granted": list(granted), "offenders": grant.check(types, granted)}


# Items the project lists as not built, with what would unblock each. One list, served to the
# Commands page; kept short and kept true (CHANGELOG records the evidence).
DEFERRED: list[dict[str, str]] = [
    {
        "item": "Harvest from a live account (kgcr review --account)",
        "why": "The AWS Config adapter is built and tested against stubbed responses and moto. "
        "It has never read a real account (no credentials here), reads five resource types and "
        "no tags, and is not wired into review.",
        "unblocks": "An account with AWS Config recording and the read-only role applied, then "
        "wiring the adapter into review and adding networks and IAM so relational defects "
        "can be evaluated.",
    },
    {
        "item": "Apply to a real account",
        "why": "The Terraform-backed apply and its refusal gates are built and tested against "
        "fakes. It has never assumed a role or called AWS. The shipped write role (ec2, s3) "
        "does not cover what generated estates create.",
        "unblocks": "Credentials, the write role applied with provision_services widened, "
        "KGCR_APPLY_ENABLED set, and a real image id in place of the placeholder.",
    },
    {
        "item": "Recorded Gemini reviews for seven variants",
        "why": "Replay covers two variants. The free tier allows 20 requests a day and the day's "
        "quota was spent verifying free-text intake.",
        "unblocks": "Run src/ml_model/record_variants.py once the quota resets; it is idempotent "
        "and stops at the first refusal.",
    },
    {
        "item": "Instructor sign-off of controls and the gold set",
        "why": "The review and sign-off tools are built. No control has been reviewed: sign-off "
        "is a human act and the six draft controls are unverified.",
        "unblocks": "A named reviewer and the instructor, working through the Controls and "
        "Gold set pages.",
    },
    {
        "item": "Human study (P11)",
        "why": "It needs ethics approval and participants. The automated half of the evaluation "
        "is in results/explainer_report.json.",
        "unblocks": "Ethics approval and recruited participants.",
    },
    {
        "item": "Weak-supervision label model (P4)",
        "why": "Checkov and Trivy now both run, but they agree with the rule floor on two of four "
        "defect families and the family mapping is this project's own.",
        "unblocks": "A decision that a label model is worth building on two engines, or a third "
        "engine (Prowler needs a live account).",
    },
]


# --- HTTP ----------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    app: App
    port: int
    server_version = "kgcr-dashboard"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (stdlib signature)
        logger.debug("%s - %s", self.address_string(), format % args)

    # responses

    def _send(
        self,
        status: int,
        body: bytes,
        ctype: str,
        *,
        sandbox: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        if sandbox:  # opened on its own, a repo file gets no scripts and no dashboard origin
            self.send_header("Content-Security-Policy", "sandbox")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _download(self, payload: Any, filename: str) -> None:
        """JSON as a file the browser saves: authoring exports are committed by a person."""
        body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self._send(
            HTTPStatus.OK,
            body,
            "application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        return host in {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def _body(self) -> dict[str, Any] | None:
        if self.headers.get("X-KGCR") != "1" or not self.headers.get("Content-Type", "").startswith(
            "application/json"
        ):
            self._error(HTTPStatus.FORBIDDEN, "requests must come from the dashboard")
            return None
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0:
            self._error(HTTPStatus.BAD_REQUEST, "bad Content-Length")
            return None
        if length > MAX_BODY:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body too large")
            return None
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._error(HTTPStatus.BAD_REQUEST, "request body is not JSON")
            return None
        if not isinstance(data, dict):
            self._error(HTTPStatus.BAD_REQUEST, "request body must be a JSON object")
            return None
        return data

    def _session(self, data: dict[str, Any]) -> dict[str, Any] | None:
        sid = data.get("session")
        session = self.app.db.session(sid) if isinstance(sid, str) else None
        if session is None:
            self._error(HTTPStatus.UNAUTHORIZED, "no such session; choose a role on the cover")
        return session

    # routing

    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "unexpected Host header")
        url = urlparse(self.path)
        path, query = url.path, parse_qs(url.query)
        try:
            if path.startswith("/api/"):
                return self._get_api(path[5:], query)
            if path.startswith("/repo/"):
                return self._repo_file(path[6:])
            return self._static(path)
        except Exception:
            logger.exception("GET %s failed", path)
            return self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR, "the server hit an error; see its log"
            )

    def _get_api(self, route: str, query: dict[str, list[str]]) -> None:
        app = self.app
        parts = route.strip("/").split("/")
        if route == "meta":
            return self._json(meta(app))
        if route == "variants":
            return self._json(variant_roster(DEFAULT_COUNT, DEFAULT_SEED))
        if route == "sessions":
            return self._json(app.db.sessions())
        if route == "jobs":
            sid = query.get("session", [None])[0]
            rows = app.db.jobs(sid)
            for r in rows:
                r["queue_position"] = app.runner.position(r["id"])
            return self._json(rows)
        if len(parts) == 2 and parts[0] == "jobs" and parts[1].isdigit():
            job = job_view(app, int(parts[1]))
            return self._json(job) if job else self._error(HTTPStatus.NOT_FOUND, "no such job")
        if route == "runs":
            from kgcr.orchestration.runstore import list_runs

            jobs_by_prefix: dict[str, list[dict[str, Any]]] = {}
            for j in app.db.jobs_with_runs():
                jobs_by_prefix.setdefault(j["run_prefix"], []).append(
                    {"id": j["id"], "catalog_no": j["catalog_no"], "session_id": j["session_id"]}
                )
            runs = list_runs(app.store_root)
            for r in runs:
                r["jobs"] = jobs_by_prefix.get(r["prefix"], [])
            return self._json(runs)
        if route == "authoring/controls":
            from kgcr.dashboard import authoring

            return self._json(authoring.controls_view(app.db))
        if route == "authoring/controls/export":
            from kgcr.dashboard import authoring

            return self._download(authoring.controls_export(app.db), "controls_review.json")
        if route == "gold":
            from kgcr.dashboard import authoring

            return self._json(authoring.gold_list(app.db))
        if route == "gold/export":
            from kgcr.dashboard import authoring

            return self._download(authoring.gold_export(app.db), "gold_set.json")
        if len(parts) == 2 and parts[0] == "gold" and parts[1].isdigit():
            from kgcr.dashboard import authoring

            try:
                return self._json(authoring.gold_get(app.db, int(parts[1])))
            except authoring.AuthoringError as exc:
                return self._error(HTTPStatus.NOT_FOUND, str(exc))
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "plans":
            return self._run_plans(parts[1])
        if len(parts) == 2 and parts[0] == "plans":
            from kgcr.plan.local import PlanRefused, load_plan

            try:
                plan = load_plan(app.store_root, parts[1])
            except PlanRefused as exc:
                return self._error(HTTPStatus.NOT_FOUND, str(exc))
            applied = _read_json(
                app.store_root / "runs" / plan["run_prefix"] / "applied" / parts[1] / "apply.json"
            )
            return self._json({"plan": plan, "apply": applied, "preflight": preflight(plan)})
        if len(parts) == 2 and parts[0] == "runs":
            from kgcr.orchestration.runstore import RunNotFound, load_run

            light = query.get("light") == ["1"]  # graph and findings only, no renderings
            try:
                run = load_run(app.store_root, parts[1], render_explanations=not light)
                run["jobs"] = [
                    j for j in app.db.jobs_with_runs() if j["run_prefix"] == run["prefix"]
                ]
                return self._json(run)
            except RunNotFound as exc:
                return self._error(HTTPStatus.NOT_FOUND, str(exc))
        if route == "reports":
            return self._json(
                {
                    name: _read_json(RESULTS / f"{name}_report.json")
                    for name in ("advisor", "recommender", "reconstruction")
                }
            )
        if route == "fixtures":
            return self._json(fixtures())
        if len(parts) == 2 and parts[0] == "fixtures":
            if not _FIXTURE_LABEL.match(parts[1]):
                return self._error(HTTPStatus.BAD_REQUEST, "not a fixture label")
            data = _read_json(FIXTURES / f"{parts[1]}.json")
            return (
                self._json(data) if data else self._error(HTTPStatus.NOT_FOUND, "no such fixture")
            )
        if route == "controls":
            from kgcr.advisor.controls import DRAFT_CONTROLS_PATH

            return self._json(_read_json(DRAFT_CONTROLS_PATH))
        if route == "environment":
            return self._json(environment(app))
        if route == "cloud":
            return self._json(cloud(app))
        if route == "project":
            return self._json(project())
        return self._error(HTTPStatus.NOT_FOUND, f"no API route {route!r}")

    def do_POST(self) -> None:  # noqa: N802 (stdlib name)
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "unexpected Host header")
        data = self._body()
        if data is None:
            return
        route = urlparse(self.path).path
        try:
            self._post_api(route, data)
        except Exception:
            logger.exception("POST %s failed", route)
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "the server hit an error; see its log")

    def _post_api(self, route: str, data: dict[str, Any]) -> None:
        app = self.app
        if route == "/api/sessions":
            role = data.get("role")
            if role not in ("user", "admin"):
                return self._error(HTTPStatus.BAD_REQUEST, "role must be user or admin")
            return self._json(app.db.create_session(role), HTTPStatus.CREATED)
        session = self._session(data)
        if session is None:
            return
        if route == "/api/jobs":
            params = data.get("params") or {}
            if not isinstance(params, dict):
                return self._error(HTTPStatus.BAD_REQUEST, "params must be an object")
            try:
                checked, live = validate(
                    str(data.get("kind")),
                    params,
                    role=session["role"],
                    live_enabled=app.live_enabled,
                )
            except JobError as exc:
                return self._error(HTTPStatus.BAD_REQUEST, str(exc))
            job_id = app.db.create_job(session["id"], str(data["kind"]), checked, live)
            app.runner.submit(job_id)
            return self._json(job_view(app, job_id), HTTPStatus.CREATED)
        parts = route.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cancel":
            job = app.db.job(int(parts[2])) if parts[2].isdigit() else None
            if job is None:
                return self._error(HTTPStatus.NOT_FOUND, "no such job")
            if session["role"] != "admin" and job["session_id"] != session["id"]:
                return self._error(
                    HTTPStatus.FORBIDDEN, "only an admin can cancel another session's job"
                )
            return self._json({"cancelled": app.runner.cancel(job["id"])})
        if route == "/api/design/extract":
            return self._extract(data, session)
        if route.startswith(("/api/authoring/", "/api/gold")):
            return self._authoring(route, data, session)
        if route == "/api/admin/live":
            if session["role"] != "admin":
                return self._error(HTTPStatus.FORBIDDEN, "only an admin can change live mode")
            enabled = data.get("enabled")
            if not isinstance(enabled, bool) or (enabled and data.get("confirm") is not True):
                return self._error(HTTPStatus.BAD_REQUEST, "enabling live mode needs confirm: true")
            app.set_live(enabled)
            logger.warning("live calls and cloud targets %s", "ENABLED" if enabled else "disabled")
            return self._json({"live_enabled": app.live_enabled})
        return self._error(HTTPStatus.NOT_FOUND, f"no API route {route!r}")

    def _run_plans(self, prefix: str) -> None:
        """A run's plans, their apply records and its lifecycle, for the Plan and apply page."""
        from kgcr.orchestration.lifecycle import read_events
        from kgcr.orchestration.runstore import RunNotFound, resolve_run

        try:
            run_dir = resolve_run(self.app.store_root, prefix)
        except RunNotFound as exc:
            return self._error(HTTPStatus.NOT_FOUND, str(exc))
        summary = _read_json(run_dir / "summary.json") or {}
        plans = [
            {
                "plan": _read_json(path),
                "apply": _read_json(run_dir / "applied" / path.parent.name / "apply.json"),
                "preflight": preflight(_read_json(path) or {}),
            }
            for path in sorted((run_dir / "plans").glob("*/plan.json"))
        ]
        return self._json(
            {
                "run_prefix": run_dir.name,
                "mode": summary.get("mode", "review"),
                "events": read_events(run_dir),
                "plans": plans,
            }
        )

    def _authoring(self, route: str, data: dict[str, Any], session: dict[str, Any]) -> None:
        """Controls review and the gold set register. Admin only, and every write is a human
        act: a typed reviewer or author name, and where it signs something off, confirm."""
        from kgcr.dashboard import authoring

        if session["role"] != "admin":
            return self._error(HTTPStatus.FORBIDDEN, "authoring is for admins")
        db = self.app.db
        parts = route.strip("/").split("/")  # api, then authoring/controls/decision or gold...
        needs_confirm = route == "/api/authoring/controls/decision" or route.endswith("/review")
        if needs_confirm and data.get("confirm") is not True:
            return self._error(HTTPStatus.BAD_REQUEST, "this is your own decision: confirm: true")
        try:
            if route == "/api/authoring/controls/decision":
                result = authoring.record_decision(
                    db,
                    data.get("control_node"),
                    data.get("decision"),
                    data.get("reviewer"),
                    data.get("note", ""),
                    data.get("proposed_summary"),
                )
                logger.warning("control decision recorded for %s", data.get("control_node"))
                return self._json(result, HTTPStatus.CREATED)
            if route == "/api/gold":
                fields = {
                    k: data.get(k)
                    for k in ("title", "framework", "source_ref", "config", "controls", "author")
                }
                return self._json(authoring.gold_create(db, **fields), HTTPStatus.CREATED)
            if len(parts) in (3, 4) and parts[1] == "gold" and parts[2].isdigit():
                entry = int(parts[2])
                action = parts[3] if len(parts) == 4 else ""
                if action == "":
                    edits = {
                        k: data[k]
                        for k in ("title", "framework", "source_ref", "config", "controls")
                        if k in data
                    }
                    return self._json(authoring.gold_update(db, entry, **edits))
                if action == "authored":
                    return self._json(authoring.gold_mark_authored(db, entry))
                if action == "check":
                    return self._json(authoring.gold_check(db, entry))
                if action == "review":
                    result = authoring.gold_review(
                        db, entry, data.get("reviewer"), data.get("note", "")
                    )
                    logger.warning("gold entry %s signed off", entry)
                    return self._json(result)
        except authoring.AuthoringError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))
        return self._error(HTTPStatus.NOT_FOUND, f"no API route {route!r}")

    def _extract(self, data: dict[str, Any], session: dict[str, Any]) -> None:
        """Ground a plain-English statement in the eight intent axes.

        Replay only, unless an admin has switched live mode on: the same spend gate as every
        job. The operator reads the evidence and confirms the form; nothing runs from here.
        """
        from kgcr.advisor.llm import DEFAULT_FIXTURE_DIR, FixtureClient, GeminiClient
        from kgcr.design.extract import ExtractionUnavailable, extract_intent

        statement = data.get("statement")
        if not isinstance(statement, str):
            return self._error(HTTPStatus.BAD_REQUEST, "statement must be text")
        live = (
            self.app.live_enabled
            and session["role"] == "admin"
            and bool(os.environ.get("GEMINI_API_KEY"))
        )
        llm = FixtureClient(DEFAULT_FIXTURE_DIR, GeminiClient() if live else None)
        try:
            result = extract_intent(statement, llm)
        except ValueError as exc:
            return self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except ExtractionUnavailable as exc:
            return self._error(HTTPStatus.BAD_GATEWAY, str(exc))
        return self._json({**result.to_dict(), "live": live})

    # files

    def _file(self, path: Path, *, sandbox: bool = False) -> None:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        if path.suffix == ".md":
            ctype = "text/plain; charset=utf-8"
        self._send(HTTPStatus.OK, path.read_bytes(), ctype, sandbox=sandbox)

    def _static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (FRONTEND / rel).resolve()
        if (
            not target.is_relative_to(FRONTEND.resolve())
            or not target.is_file()
            or target.suffix == ".py"
        ):
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        self._file(target)

    def _repo_file(self, rel: str) -> None:
        top = rel.split("/", 1)[0]
        target = (ROOT / rel).resolve()
        allowed = REPO_FILES.get(top)
        if (
            allowed is None
            or target.suffix not in allowed
            or not target.is_relative_to((ROOT / top).resolve())
            or not target.is_file()
        ):
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        self._file(target, sandbox=True)


def make_server(port: int, store_root: Path, app: App | None = None) -> ThreadingHTTPServer:
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("font/woff2", ".woff2")
    # Absolute, because job children run with cwd=ROOT and would resolve a relative path there.
    shared = app or App(store_root.resolve())

    class BoundHandler(Handler):
        app = shared

    server = ThreadingHTTPServer(("127.0.0.1", port), BoundHandler)
    BoundHandler.port = server.server_address[1]  # port 0 binds an ephemeral port (tests)
    return server


def _warm_up() -> None:
    """Pay the first-request import and corpus cost before the operator opens the cover."""
    try:
        import kgcr.orchestration.runstore  # noqa: F401 (import for its side effect)

        variant_roster(DEFAULT_COUNT, DEFAULT_SEED)
    except Exception:  # fail soft: the first request simply pays the cost instead
        logger.exception("dashboard warm-up failed")


def serve(port: int, store_root: Path, open_browser: bool = False) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = App(store_root.resolve())
    server = make_server(port, store_root, app)
    threading.Thread(target=_warm_up, name="kgcr-warm-up", daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"KGCR dashboard on {url}  (replay mode; Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.runner.shutdown()  # a child must not outlive the server and overlap the next run
        server.server_close()
    return 0
