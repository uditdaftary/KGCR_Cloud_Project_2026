"""``kgcr`` command-line surface.

The subcommands mirror the planned interface in the README
(``design``/``review``/``explain``/``plan``/``apply``/``history``). At Phase 0
they are declared but not implemented: each exits with a clear "planned for
Phase N" message so the interface shape is real and testable while the
subsystems behind it are built.

Working today:

* ``kgcr --version`` prints the package version.
* ``kgcr repro-info`` prints the seed report and version fingerprint that go
  into every run record — the fastest way to confirm an environment is pinned.
* ``kgcr review`` runs review mode end to end, locally: harvest stand-in, graph,
  intent reconstruction, recommendation, advisor loop, explanation, stored run.
* ``kgcr history`` lists stored runs; ``kgcr explain`` re-renders one for an audience.
* ``kgcr dashboard`` serves the local dashboard that drives all of the above.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict

from kgcr._version import __version__
from kgcr.advisor.llm import load_local_env
from kgcr.repro import DEFAULT_SEED, seed_everything
from kgcr.versions import tool_versions

# Exit code used for a command that exists in the interface but is not yet
# implemented. Distinct from argparse's usage error (2) so scripts can tell the
# difference between "you typed it wrong" and "not built yet".
EXIT_NOT_IMPLEMENTED = 3

# subcommand -> (help text, phase it lands in)
_PLANNED: dict[str, tuple[str, str]] = {
    "plan": ("Produce a terraform plan for a spec", "P3/P10"),
    "apply": ("Apply a previously produced plan", "P10"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kgcr",
        description="Knowledge Graph-Based Cloud Configuration Recommendation.",
    )
    parser.add_argument("--version", action="version", version=f"kgcr {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    repro = sub.add_parser(
        "repro-info",
        help="Print the seed report and version fingerprint for this environment",
    )
    repro.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"Seed to apply (default {DEFAULT_SEED})"
    )
    repro.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    repro.set_defaults(func=_cmd_repro_info)

    # Research/dev tooling — not part of the product surface. Generates Corpus A
    # (Phase 3): intent-first synthetic estates, parsed into the graph.
    corpus = sub.add_parser("corpus", help="[dev] Generate Corpus A synthetic estates (P3)")
    corpus.add_argument("--count", type=int, default=500, help="Number of estates (default 500)")
    corpus.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"Base seed (default {DEFAULT_SEED})"
    )
    corpus.add_argument(
        "--family-size", type=int, default=1, help="Estates per seed family (default 1)"
    )
    corpus.add_argument(
        "--out", type=str, default=None, help="Write the corpus to this directory (optional)"
    )
    corpus.add_argument("--json", action="store_true", help="Emit the summary as JSON")
    corpus.set_defaults(func=_cmd_corpus)

    review = sub.add_parser(
        "review",
        help="Review an estate end to end, locally (harvest stand-in -> explain)",
    )
    review.add_argument(
        "--variant",
        default="unencrypted_database",
        help="Defect to inject into the held-out estate (default: DF-2; DF-7 variants need "
        "recorded LLM fixtures to be found)",
    )
    review.add_argument(
        "--audience", choices=("architect", "auditor", "learner"), default="architect"
    )
    review.add_argument("--out", default="runs-local", help="Artifact store root (S3 stand-in)")
    review.add_argument(
        "--s3-bucket", default=None, help="Store artifacts in this S3 bucket instead (aws extra)"
    )
    review.add_argument(
        "--sns-topic-arn", default=None, help="Publish contested runs to this SNS topic (aws extra)"
    )
    review.add_argument("--count", type=int, default=180, help="Corpus size (default 180)")
    review.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Corpus seed")
    review.set_defaults(func=_cmd_review)

    design = sub.add_parser(
        "design",
        help="Design a configuration from a stated workload intent, locally (every axis required)",
    )
    from kgcr.design.intake import AXES, axis_choices

    for axis, allowed in axis_choices().items():
        design.add_argument(
            f"--{axis.replace('_', '-')}",
            dest=axis,
            default=None,
            metavar="{" + "|".join(allowed) + "}",
            help=f"{axis} (required)",
        )
    design.add_argument(
        "--audience", choices=("architect", "auditor", "learner"), default="architect"
    )
    design.add_argument(
        "--statement",
        default=None,
        help="Describe the workload in words; the model fills only axes it can quote from the "
        "text, and flags you give win. Any axis left unstated is refused, never defaulted",
    )
    design.add_argument(
        "--extract-only",
        action="store_true",
        help="With --statement: print the grounded extraction as JSON and stop",
    )
    design.add_argument("--out", default="runs-local", help="Artifact store root (S3 stand-in)")
    design.add_argument("--count", type=int, default=180, help="Corpus size (default 180)")
    design.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Corpus seed")
    design.set_defaults(func=_cmd_design)
    assert set(AXES) == set(axis_choices())  # the flags above cover every intent axis

    history = sub.add_parser("history", help="List review runs in the local artifact store")
    history.add_argument("--out", default="runs-local", help="Artifact store root")
    history.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    history.set_defaults(func=_cmd_history)

    explain = sub.add_parser("explain", help="Re-render a stored run for an audience")
    explain.add_argument("--run", required=True, help="Run id or unique prefix (see history)")
    explain.add_argument(
        "--audience", choices=("architect", "auditor", "learner"), default="architect"
    )
    explain.add_argument("--out", default="runs-local", help="Artifact store root")
    explain.set_defaults(func=_cmd_explain)

    dashboard = sub.add_parser("dashboard", help="Serve the local dashboard on 127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8765, help="Port (default 8765)")
    dashboard.add_argument("--out", default="runs-local", help="Artifact store root")
    dashboard.add_argument("--open", action="store_true", help="Open the browser on start")
    dashboard.set_defaults(func=_cmd_dashboard)

    for name, (help_text, phase) in _PLANNED.items():
        p = sub.add_parser(name, help=f"{help_text} (planned, {phase})")
        p.set_defaults(func=_make_not_implemented(name, phase))

    return parser


def _make_not_implemented(name: str, phase: str) -> Callable[[argparse.Namespace], int]:
    def _run(_args: argparse.Namespace) -> int:
        print(
            f"kgcr {name}: not implemented yet — planned for Phase {phase}.",
            file=sys.stderr,
        )
        return EXIT_NOT_IMPLEMENTED

    return _run


def _cmd_repro_info(args: argparse.Namespace) -> int:
    report = seed_everything(args.seed)
    payload = {"seed_report": asdict(report), "tool_versions": tool_versions()}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"seed:            {report.seed}")
    print(f"python_random:   {report.python_random}")
    print(f"PYTHONHASHSEED:  {'fixed' if report.pythonhashseed else 'NOT fixed'}")
    print(f"numpy seeded:    {report.numpy}")
    print(f"torch seeded:    {report.torch}")
    print("tool versions:")
    for key, value in sorted(payload["tool_versions"].items()):
        print(f"  {key}: {value}")
    return 0


def _cmd_corpus(args: argparse.Namespace) -> int:
    # Imported lazily so the reproducibility commands do not pull in the corpus
    # stack (and so `kgcr --help` stays fast).
    from kgcr.corpus.pipeline import generate_corpus, summarise_corpus, write_corpus

    estates = generate_corpus(args.count, args.seed, family_size=args.family_size)

    if args.out is not None:
        manifest = write_corpus(estates, args.out)
        summary = manifest["summary"]
    else:
        summary = summarise_corpus(estates)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print(f"estates:             {summary['estates']}")
    print(f"unique estate ids:   {summary['unique_estate_ids']}")
    print(f"seed families:       {summary['seed_families']}")
    print(f"total resources:     {summary['total_resources']}")
    print(f"graph nodes / edges: {summary['total_graph_nodes']} / {summary['total_graph_edges']}")
    print("archetype distribution:")
    for name, n in summary["archetypes"].items():
        print(f"  {name}: {n}")
    if args.out is not None:
        print(f"written to:          {args.out}")
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    from pathlib import Path

    from kgcr.orchestration.runstore import list_runs

    runs = list_runs(Path(args.out))
    if args.json:
        print(json.dumps(runs, indent=2, sort_keys=True))
        return 0
    if not runs:
        print(f"no stored runs under {args.out}; try `kgcr review`")
        return 0
    for r in runs:
        print(
            f"{r['prefix']}  {r['created_at'][:19]}  {r['loop_status']:<9}  "
            f"{len(r['severities'])} finding(s)  {r['variant'] or '-'}"
        )
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    from pathlib import Path

    from kgcr.orchestration.runstore import RunNotFound, load_run

    try:
        run = load_run(Path(args.out), args.run)
    except RunNotFound as exc:
        print(f"kgcr explain: {exc}", file=sys.stderr)
        return 2
    print(run["explanations"][args.audience])
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from pathlib import Path

    from kgcr.dashboard.server import serve

    return serve(port=args.port, store_root=Path(args.out), open_browser=args.open)


def _cmd_design(args: argparse.Namespace) -> int:
    import logging
    from pathlib import Path

    from kgcr.advisor.llm import default_llm
    from kgcr.design.intake import AXES, IntakeError, axis_choices, build_intent
    from kgcr.explainer.explainer import render
    from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier
    from kgcr.orchestration.design import run_design

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    stated = {axis: getattr(args, axis) for axis in AXES}
    if args.extract_only and not args.statement:
        print("kgcr design: --extract-only needs --statement", file=sys.stderr)
        return 2
    if args.statement:
        from kgcr.design.extract import extract_intent

        try:
            extraction = extract_intent(args.statement, default_llm())
        except ValueError as exc:
            print(f"kgcr design: {exc}", file=sys.stderr)
            return 2
        if args.extract_only:
            print(json.dumps(extraction.to_dict(), indent=2, sort_keys=True))
            return 0
        print(f"[0/5] extract     model status: {extraction.llm_status}")
        for axis in AXES:
            got = extraction.fields[axis]
            if got.value is None:
                why = extraction.rejected.get(axis, "not stated")
                print(f"      {axis:<15} none ({why})")
            else:
                print(f'      {axis:<15} {got.value}  <- "{got.evidence}"')
            if stated[axis] is None:  # a flag you gave always wins over the statement
                stated[axis] = got.value
    try:
        intent = build_intent(stated)
    except IntakeError as exc:
        # No defaults: an unstated requirement must be stated, not assumed (FD-01 S1a).
        print(f"kgcr design: {exc}", file=sys.stderr)
        choices = axis_choices()
        for axis in (*exc.missing, *exc.invalid):
            if axis in choices:
                print(f"  {axis}: one of {', '.join(choices[axis])}", file=sys.stderr)
        return 2
    run = run_design(
        intent=intent,
        store=LocalArtifactStore(Path(args.out)),
        notifier=LogNotifier(),
        llm=default_llm(),
        count=args.count,
        seed=args.seed,
    )
    estate = run.candidate.estate
    print(f"[1/5] intake      stated intent, {len(AXES)} axes, none defaulted")
    print(f"[2/5] synthesize  estate {estate.estate_id}, {len(estate.resources)} resources")
    print(
        f"      recommender audit: {len(run.candidate.applied)} option(s) applied, "
        f"{len(run.candidate.reported_missing)} recommended but not added, "
        f"{len(run.candidate.reported_unexpected)} in spec but not recommended"
    )
    print(f"[3/5] graph       {run.graph_nodes} nodes, {run.graph_edges} dependency edges")
    print(
        f"[4/5] advise      LLM: {run.llm_mode}; loop {run.loop.status} ({run.loop.reason}) "
        f"after {len(run.loop.passes)} pass(es)"
    )
    if run.llm_mode != "ok":
        print("      rule floor only on at least one pass: relational (DF-7) and resilience")
        print("      (DF-5) findings need the LLM advisor, so they are not reported on every pass")
    for f in run.reviewed_findings:
        print(f"      [{f.severity.value}] {f.control_node} on {', '.join(f.affected_elements)}")
    print(f"[5/5] explain     audience={args.audience}; run {run.record.run_id[:16]}")
    for name, uri in run.artifacts.items():
        print(f"      stored {name}: {uri}")
    print()
    print(render(run.bundle, args.audience))
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    # Lazy imports: the ML stack is only needed for this command.
    import logging
    from pathlib import Path

    from kgcr.explainer.explainer import render
    from kgcr.orchestration.aws import (
        ArtifactStore,
        LocalArtifactStore,
        LogNotifier,
        Notifier,
        S3ArtifactStore,
        SnsNotifier,
    )
    from kgcr.orchestration.review import default_llm, run_review

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Local stand-ins unless AWS targets are named explicitly: no flag, no AWS call.
    store: ArtifactStore = (
        S3ArtifactStore(args.s3_bucket) if args.s3_bucket else LocalArtifactStore(Path(args.out))
    )
    notifier: Notifier = SnsNotifier(args.sns_topic_arn) if args.sns_topic_arn else LogNotifier()
    run = run_review(
        variant=args.variant,
        store=store,
        notifier=notifier,
        llm=default_llm(),
        count=args.count,
        seed=args.seed,
    )
    estate = run.target.estate
    print("[1/6] harvest   local stand-in for AWS Config (no AWS call)")
    print(f"      estate {estate.estate_id}, held-out split, {len(estate.resources)} resources")
    defect = run.target.defect
    print(f"      injected for the demo: {defect.variant} ({defect.defect_class})")
    print(f"[2/6] graph     {run.graph_nodes} nodes, {run.graph_edges} dependency edges")
    fields = ", ".join(f"{f}={run.intent.value(f)}" for f in sorted(run.intent.fields))
    print(f"[3/6] intent    {fields}")
    if run.escalated:
        print(f"      low confidence, confirm with the user: {', '.join(run.escalated)}")
    chosen = sum(r.score >= 0.5 for r in run.recommended)
    print(
        f"[4/6] recommend {chosen} options recommended (score >= 0.5) of "
        f"{len(run.recommended)} ranked after the CRITICAL mask"
    )
    for option in run.missing_from_estate:
        print(f"      recommended, not in estate: {option}")
    for option in run.unexpected_in_estate:
        print(f"      in estate, not recommended: {option}")
    print(
        f"[5/6] advise    LLM: {run.llm_mode}; loop {run.loop.status} ({run.loop.reason}) "
        f"after {len(run.loop.passes)} pass(es)"
    )
    if run.llm_mode != "ok":
        print("      rule floor only on at least one pass: relational (DF-7) and resilience")
        print("      (DF-5) findings need the LLM advisor, so they are not reported on every pass")
    for f in run.reviewed_findings:
        where = ", ".join(f.affected_elements)
        print(f"      [{f.severity.value}] {f.control_node} on {where} ({f.origin})")
    print(f"[6/6] explain   audience={args.audience}; run {run.record.run_id[:16]}")
    for name, uri in run.artifacts.items():
        print(f"      stored {name}: {uri}")
    print()
    print(render(run.bundle, args.audience))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:  # real CLI invocation; tests pass argv explicitly and skip .env
        load_local_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    result: int = args.func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
