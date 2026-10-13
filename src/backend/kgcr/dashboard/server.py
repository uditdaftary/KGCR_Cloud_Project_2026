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
import shutil
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from kgcr._version import __version__
from kgcr.advisor.llm import DEFAULT_FIXTURE_DIR
from kgcr.dashboard.db import Database
from kgcr.dashboard.jobs import JOB_KINDS, ROOT, JobError, Runner, validate
from kgcr.repro import DEFAULT_COUNT, DEFAULT_SEED

__all__ = ["make_server", "serve"]

logger = logging.getLogger(__name__)

FRONTEND = ROOT / "src" / "frontend"
RESULTS = ROOT / "results"
FIXTURE_DIR = DEFAULT_FIXTURE_DIR
# Read-only project files the dashboard may show, by directory and extension.
REPO_FILES = {"architecture": {".png", ".svg"}, "docs": {".md"}, "dataset": {".md"}}
MAX_BODY = 64 * 1024
_FIXTURE_LABEL = re.compile(r"^v1(-[a-z0-9]{1,32}){1,4}$")
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
        except ValueError:
            target = None
        if target is not None:
            estate_id = target.estate.estate_id
            g = build_graph_from_estate(target.estate)
            graph = {
                "nodes": [{"address": n.address, "type": n.type} for n in g.nodes],
                "edges": [[e.source, e.target] for e in g.edges],
            }
            seeded = list(target.defect.evidence_path or target.defect.injection_site)
        fixture = estate_id is not None and any(FIXTURE_DIR.glob(f"v1-{estate_id}-loop-p*.json"))
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
    from kgcr.cli import _PLANNED
    from kgcr.explainer.explainer import AUDIENCES

    return {
        "version": __version__,
        "audiences": list(AUDIENCES),
        "default_seed": DEFAULT_SEED,
        "default_count": DEFAULT_COUNT,
        "live_enabled": app.live_enabled,
        "live_call_cap": LIVE_CALL_CAP,
        "gemini_model": GEMINI_MODEL,
        "gemini_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "planned": [{"command": k, "help": h, "phase": p} for k, (h, p) in _PLANNED.items()],
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
    if job.get("output_dir"):
        for path in sorted(Path(job["output_dir"]).glob("*.json")):
            if path.stat().st_size < 1_000_000:
                outputs[path.name] = _read_json(path)
    job["outputs"] = outputs
    return job


def environment() -> dict[str, Any]:
    from dataclasses import asdict

    from kgcr.repro import seed_everything
    from kgcr.versions import tool_versions

    return {
        "seed_report": asdict(seed_everything(DEFAULT_SEED)),
        "tool_versions": tool_versions(),
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
    return {
        "terraform_files": sorted(p.name for p in (ROOT / "src" / "aws").glob("*.tf")),
        "resources": resources,
        "terraform_installed": shutil.which("terraform") is not None,
        "boto3_installed": importlib.util.find_spec("boto3") is not None,
        "live_enabled": app.live_enabled,
        "deployed": False,
    }


def fixtures() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        data = _read_json(path)
        kind = path.stem.split("-")[1]
        rows.append(
            {
                "label": path.stem,
                "kind": {"syc": "sycophancy trial", "clean": "clean estate"}.get(
                    kind, "review loop"
                ),
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


# --- HTTP ----------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    app: App
    port: int
    server_version = "kgcr-dashboard"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (stdlib signature)
        logger.debug("%s - %s", self.address_string(), format % args)

    # responses

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

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
        if len(parts) == 2 and parts[0] == "runs":
            from kgcr.orchestration.runstore import RunNotFound, load_run

            try:
                return self._json(load_run(app.store_root, parts[1]))
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
            data = _read_json(FIXTURE_DIR / f"{parts[1]}.json")
            return (
                self._json(data) if data else self._error(HTTPStatus.NOT_FOUND, "no such fixture")
            )
        if route == "controls":
            from kgcr.advisor.controls import DRAFT_CONTROLS_PATH

            return self._json(_read_json(DRAFT_CONTROLS_PATH))
        if route == "environment":
            return self._json(environment())
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

    # files

    def _file(self, path: Path) -> None:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        if path.suffix == ".md":
            ctype = "text/plain; charset=utf-8"
        self._send(HTTPStatus.OK, path.read_bytes(), ctype)

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
        self._file(target)


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
