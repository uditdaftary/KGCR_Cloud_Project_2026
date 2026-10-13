"""Allow-listed jobs the dashboard can run, their parameter validation, and the worker.

Every job is a subprocess with an argument list (never a shell), run one at a time
so two jobs never race on the same files. Jobs write into their own directory
under ``<store>/jobs/KG<no>/``; nothing the dashboard runs overwrites the committed
``results/`` evidence or ``dataset/processed/``.

The child environment is built explicitly: ``KGCR_LLM_LIVE`` is always set, and the
Gemini key and AWS credentials are passed through only to a job the admin has
cleared for live calls or real cloud targets.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kgcr.advisor.llm import DEFAULT_FIXTURE_DIR
from kgcr.dashboard.db import Database, now_iso
from kgcr.repro import DEFAULT_COUNT, DEFAULT_SEED

__all__ = ["JOB_KINDS", "JobError", "JobKind", "Param", "Runner", "validate"]

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[4]
ML = ROOT / "src" / "ml_model"
FIXTURES = DEFAULT_FIXTURE_DIR  # honours KGCR_LLM_FIXTURE_DIR, like the child processes do
MAX_LOG_CHARS = 200_000

_SECRET_NAMES = (
    "GEMINI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)
_S3_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")
_SNS_ARN = re.compile(r"^arn:aws[a-z\-]*:sns:[a-z0-9\-]+:\d{12}:[A-Za-z0-9_\-]{1,256}$")


class JobError(ValueError):
    """A job request the dashboard refuses; the message is shown to the operator."""


@dataclass(frozen=True, slots=True)
class Param:
    kind: str  # "int" | "choice" | "bool" | "s3_bucket" | "sns_arn"
    default: Any = None
    low: int = 0
    high: int = 0
    choices: tuple[str, ...] = ()
    admin_only: bool = False
    label: str = ""

    def coerce(self, name: str, value: Any) -> Any:
        if self.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int | str):
                raise JobError(f"{name} must be a whole number")
            try:
                number = int(value)
            except ValueError:
                raise JobError(f"{name} must be a whole number") from None
            if not self.low <= number <= self.high:
                raise JobError(f"{name} must be between {self.low} and {self.high}")
            return number
        if self.kind == "choice":
            if value not in self.choices:
                raise JobError(f"{name} must be one of: {', '.join(self.choices)}")
            return value
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise JobError(f"{name} must be true or false")
            return value
        if value in (None, ""):
            return None
        pattern = _S3_BUCKET if self.kind == "s3_bucket" else _SNS_ARN
        if not isinstance(value, str) or not pattern.fullmatch(value):  # `$` accepts a trailing \n
            raise JobError(f"{name} is not a valid {self.label or self.kind}")
        return value


Argv = Callable[[dict[str, Any], Path, Path], list[list[str]]]


@dataclass(frozen=True, slots=True)
class JobKind:
    label: str
    summary: str
    writes: str
    argv: Argv
    params: dict[str, Param] = field(default_factory=dict)
    admin_only: bool = True
    can_go_live: bool = False


def _py(*args: str) -> list[str]:
    return [sys.executable, *args]


def _review_argv(p: dict[str, Any], out: Path, store: Path) -> list[list[str]]:
    argv = _py("-m", "kgcr.cli", "review", "--variant", p["variant"], "--audience", p["audience"])
    argv += ["--count", str(p["count"]), "--seed", str(p["seed"]), "--out", str(store)]
    if p.get("s3_bucket"):
        argv += ["--s3-bucket", p["s3_bucket"]]
    if p.get("sns_topic_arn"):
        argv += ["--sns-topic-arn", p["sns_topic_arn"]]
    return [argv]


def _gates_argv(_p: dict[str, Any], _out: Path, _store: Path) -> list[list[str]]:
    # The CI gate order (CLAUDE.md); the runner stops at the first failure.
    return [
        _py("-m", "ruff", "check", "."),
        _py("-m", "ruff", "format", "--check", "."),
        _py("-m", "mypy"),
        _py("-m", "pytest", "-q"),
    ]


def _variants() -> tuple[str, ...]:
    from kgcr.defects.inject import INJECTORS

    return tuple(i.variant for i in INJECTORS)


_COUNT = Param("int", DEFAULT_COUNT, 20, 2000, label="Corpus size")
_SEED = Param("int", DEFAULT_SEED, 0, 2**31 - 1, label="Corpus seed")
_LIVE = Param("bool", False, admin_only=True, label="Live Gemini calls")

JOB_KINDS: dict[str, JobKind] = {
    "review": JobKind(
        label="Review an estate",
        summary="kgcr review: harvest, graph, intent, recommend, advise, explain.",
        writes="<store>/runs/<run id>/",
        argv=_review_argv,
        params={
            "variant": Param(
                "choice", "unencrypted_database", choices=_variants(), label="Variant"
            ),
            "audience": Param(
                "choice", "architect", choices=("architect", "auditor", "learner"), label="Audience"
            ),
            "count": _COUNT,
            "seed": _SEED,
            "live": _LIVE,
            "s3_bucket": Param("s3_bucket", None, admin_only=True, label="S3 bucket"),
            "sns_topic_arn": Param("sns_arn", None, admin_only=True, label="SNS topic ARN"),
        },
        admin_only=False,
        can_go_live=True,
    ),
    "corpus": JobKind(
        label="Generate corpus",
        summary="kgcr corpus: intent-first synthetic estates parsed into graphs.",
        writes="<job dir>/corpus/",
        argv=lambda p, out, _s: [
            _py("-m", "kgcr.cli", "corpus", "--count", str(p["count"]), "--seed", str(p["seed"]))
            + ["--family-size", str(p["family_size"]), "--out", str(out / "corpus"), "--json"]
        ],
        params={
            "count": Param("int", 500, 10, 2000, label="Estates"),
            "seed": _SEED,
            "family_size": Param("int", 1, 1, 10, label="Family size"),
        },
    ),
    "advisor_eval": JobKind(
        label="Evaluate the advisor",
        summary="run_advisor.py: seeded recall, sycophancy trials, clean-estate criticals.",
        writes="<job dir>/advisor_report.json",
        argv=lambda p, out, _s: [
            _py(str(ML / "run_advisor.py"), "--count", str(p["count"]), "--seed", str(p["seed"]))
            + ["--report-out", str(out / "advisor_report.json")]
        ],
        params={"count": _COUNT, "seed": _SEED, "live": _LIVE},
        can_go_live=True,
    ),
    "reconstruction_train": JobKind(
        label="Train the intent reconstructor",
        summary="train.py: per-axis random forests, held-out accuracy and calibration.",
        writes="<job dir>/model.pkl, reconstruction_report.json",
        argv=lambda p, out, _s: [
            _py(str(ML / "train.py"), "--count", str(p["count"]), "--seed", str(p["seed"]))
            + ["--model-out", str(out / "model.pkl")]
            + ["--report-out", str(out / "reconstruction_report.json")]
        ],
        # --seed is the corpus seed; the forest's random_state keeps train.py's own default.
        params={"count": _COUNT, "seed": _SEED},
    ),
    "recommender_eval": JobKind(
        label="Evaluate the recommender",
        summary="train_recommender.py: the model against three baselines on held-out estates.",
        writes="<job dir>/recommender_report.json",
        argv=lambda p, out, _s: [
            _py(str(ML / "train_recommender.py"), "--count", str(p["count"]))
            + ["--seed", str(p["seed"]), "--report-out", str(out / "recommender_report.json")]
        ],
        params={"count": _COUNT, "seed": _SEED},
    ),
    "predict": JobKind(
        label="Predict one estate's intent",
        summary="predict.py: recovered value and confidence per intent axis.",
        writes="nothing (log only)",
        argv=lambda p, _o, _s: [
            _py(str(ML / "predict.py"), "--index", str(p["index"]), "--seed", str(p["seed"]))
        ],
        params={"index": Param("int", 0, 0, 1999, label="Estate index"), "seed": _SEED},
    ),
    "gates": JobKind(
        label="Run the quality gates",
        summary="ruff check, ruff format --check, mypy, pytest, as CI runs them.",
        writes="nothing (log only)",
        argv=_gates_argv,
    ),
    "static_report": JobKind(
        label="Build the static results page",
        summary="build_dashboard.py: the offline results page for the submission.",
        writes="<job dir>/dashboard.html",
        argv=lambda _p, out, _s: [
            _py(str(ROOT / "src" / "frontend" / "build_dashboard.py"))
            + ["--out", str(out / "dashboard.html")]
        ],
    ),
}


def validate(
    kind: str, raw: dict[str, Any], *, role: str, live_enabled: bool
) -> tuple[dict[str, Any], bool]:
    """Checked parameters and whether the job runs live; raises :class:`JobError`."""
    spec = JOB_KINDS.get(kind)
    if spec is None:
        raise JobError(f"unknown job: {kind!r}")
    if spec.admin_only and role != "admin":
        raise JobError(f"{spec.label} is an admin job")
    unknown = set(raw) - set(spec.params)
    if unknown:
        raise JobError(f"unknown parameter(s): {', '.join(sorted(unknown))}")
    params: dict[str, Any] = {}
    for name, param in spec.params.items():
        if name in raw and param.admin_only and role != "admin":
            raise JobError(f"{param.label or name} is admin only")
        params[name] = param.coerce(name, raw.get(name, param.default))
    cloud = bool(params.get("s3_bucket") or params.get("sns_topic_arn"))
    live = bool(params.get("live")) or cloud
    if live and not live_enabled:
        raise JobError("live calls and cloud targets are switched off; enable them in KG 026")
    return params, live


class Runner:
    """A single worker thread that executes queued jobs in order."""

    def __init__(
        self,
        db: Database,
        store_root: Path,
        live_allowed: Callable[[], bool] = lambda: False,
    ) -> None:
        self.db = db
        self.store_root = store_root
        # Asked again when a live job reaches the front, so switching live off stops queued spend.
        self._live_allowed = live_allowed
        self._queue: queue.Queue[int] = queue.Queue()
        self._lock = threading.Lock()
        self._logs: dict[int, list[str]] = {}
        self._procs: dict[int, subprocess.Popen[str]] = {}
        self._cancelled: set[int] = set()
        self._pending: list[int] = []
        self._active: set[int] = set()
        self._stopping = False
        threading.Thread(target=self._work, name="kgcr-jobs", daemon=True).start()

    def shutdown(self) -> None:
        """Stop the running child and start nothing further, so no job outlives the server."""
        with self._lock:
            self._stopping = True
            self._cancelled.update(self._active)
            procs = list(self._procs.values())
        for proc in procs:
            proc.terminate()

    def submit(self, job_id: int) -> None:
        with self._lock:
            self._pending.append(job_id)
        self._queue.put(job_id)

    def position(self, job_id: int) -> int | None:
        """1-based place in the queue, or None once running or finished."""
        with self._lock:
            return self._pending.index(job_id) + 1 if job_id in self._pending else None

    def live_log(self, job_id: int) -> str | None:
        with self._lock:
            lines = self._logs.get(job_id)
            return None if lines is None else "".join(lines)

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            queued = job_id in self._pending
            active = job_id in self._active
            if queued or active:
                self._cancelled.add(job_id)
            if queued:  # off the queue now, so it stops reporting a place in it
                self._pending.remove(job_id)
            proc = self._procs.get(job_id)
        if proc is not None:
            proc.terminate()
            return True
        if queued:
            self.db.update_job(job_id, status="cancelled", finished_at=now_iso())
            return True
        return active  # picked up but not spawned yet: _run sees the flag before it launches

    def _env(self, live: bool, cloud: bool = False) -> dict[str, str]:
        """Child environment. ``live`` grants the Gemini key, ``cloud`` the AWS credentials.

        Withheld names are blanked, not deleted: the child's ``load_dotenv(override=False)``
        refills a missing name from ``.env`` but leaves an existing (empty) one alone.
        """
        granted = (("GEMINI_",) if live else ()) + (("AWS_",) if cloud else ())
        env = dict(os.environ)
        for name in {*os.environ, *_SECRET_NAMES}:  # names a .env could add even if unset here
            if name.startswith(("AWS_", "GEMINI_")) and not name.startswith(granted):
                env[name] = ""
        env.update(
            KGCR_LLM_LIVE="1" if live else "0",
            PYTHONHASHSEED="0",
            PYTHONUTF8="1",
            PYTHONUNBUFFERED="1",
        )
        return env

    def _work(self) -> None:
        while True:
            job_id = self._queue.get()
            with self._lock:
                if job_id in self._pending:
                    self._pending.remove(job_id)
                if self._stopping:
                    return
                skip = job_id in self._cancelled
                if not skip:
                    self._active.add(job_id)
            if skip:
                continue
            try:
                self._run(job_id)
            except Exception as exc:  # the worker must outlive any one job
                logger.exception("job %s crashed the runner", job_id)
                self.db.update_job(
                    job_id, status="failed", finished_at=now_iso(), log=f"[dashboard] {exc}\n"
                )
            finally:
                with self._lock:
                    self._active.discard(job_id)
                    self._logs.pop(job_id, None)
                    self._procs.pop(job_id, None)

    def _run(self, job_id: int) -> None:
        job = self.db.job(job_id)
        if job is None:
            return
        if job["live"] and not self._live_allowed():
            self.db.update_job(
                job_id,
                status="cancelled",
                finished_at=now_iso(),
                log="[dashboard] live mode was switched off before this job started\n",
            )
            return
        spec = JOB_KINDS[job["kind"]]
        params = job["params"]
        live = bool(params.get("live"))
        cloud = bool(params.get("s3_bucket") or params.get("sns_topic_arn"))
        out = self.store_root / "jobs" / f"KG{job['catalog_no']}"
        out.mkdir(parents=True, exist_ok=True)
        before = set(FIXTURES.glob("*.json")) if job["live"] else set()
        self.db.update_job(job_id, status="running", started_at=now_iso(), output_dir=str(out))
        with self._lock:
            self._logs[job_id] = []
        code = 0
        stopped_early = False
        for argv in spec.argv(params, out, self.store_root):
            self._append(job_id, "$ python " + " ".join(argv[1:]) + "\n")
            # Check and spawn under one lock so a cancel lands either before the check or
            # after the process is registered, never in between.
            with self._lock:
                if job_id in self._cancelled or self._stopping:
                    stopped_early = True
                    break
                proc = subprocess.Popen(
                    argv,
                    cwd=ROOT,
                    env=self._env(live, cloud),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self._procs[job_id] = proc
            assert proc.stdout is not None
            for line in proc.stdout:
                self._append(job_id, line)
            code = proc.wait()
            with self._lock:
                self._procs.pop(job_id, None)
            if code != 0:
                break
        with self._lock:
            log = "".join(self._logs.pop(job_id, []))[-MAX_LOG_CHARS:]
            cancelled = job_id in self._cancelled
        # A cancel that arrived after the last step finished cleanly does not undo the result.
        status = (
            "cancelled"
            if cancelled and (stopped_early or code != 0)
            else ("done" if code == 0 else "failed")
        )
        self.db.update_job(
            job_id,
            status=status,
            exit_code=code,
            finished_at=now_iso(),
            log=log,
            run_prefix=_run_prefix(log),
            live_calls=len(set(FIXTURES.glob("*.json")) - before) if job["live"] else None,
        )

    def _append(self, job_id: int, line: str) -> None:
        with self._lock:
            self._logs.setdefault(job_id, []).append(line)


_STORED_BUNDLE = re.compile(r"stored bundle: .*?runs[\\/]([0-9a-f]{16})[\\/]bundle\.json")


def _run_prefix(log: str) -> str | None:
    match = _STORED_BUNDLE.search(log)
    return match.group(1) if match else None
