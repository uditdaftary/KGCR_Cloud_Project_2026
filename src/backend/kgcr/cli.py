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
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict

from kgcr._version import __version__
from kgcr.repro import DEFAULT_SEED, seed_everything
from kgcr.versions import tool_versions

# Exit code used for a command that exists in the interface but is not yet
# implemented. Distinct from argparse's usage error (2) so scripts can tell the
# difference between "you typed it wrong" and "not built yet".
EXIT_NOT_IMPLEMENTED = 3

# subcommand -> (help text, phase it lands in)
_PLANNED: dict[str, tuple[str, str]] = {
    "design": ("Recommend a configuration from a stated intent", "P6/P7"),
    "explain": ("Explain a run as a reasoning subgraph", "P9"),
    "plan": ("Produce a terraform plan for a spec", "P3/P10"),
    "apply": ("Apply a previously produced plan", "P10"),
    "history": ("Show run history for an account", "P10"),
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
        default="indirect_internet_reachability",
        help="Defect to inject into the held-out estate (default: a DF-7 relational path)",
    )
    review.add_argument(
        "--audience", choices=("architect", "auditor", "learner"), default="architect"
    )
    review.add_argument("--out", default="runs-local", help="Artifact store root (S3 stand-in)")
    review.add_argument("--count", type=int, default=180, help="Corpus size (default 180)")
    review.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Corpus seed")
    review.set_defaults(func=_cmd_review)

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


def _cmd_review(args: argparse.Namespace) -> int:
    # Lazy imports: the ML stack is only needed for this command.
    import logging
    from pathlib import Path

    from kgcr.explainer.explainer import render
    from kgcr.orchestration.aws import LocalArtifactStore, LogNotifier
    from kgcr.orchestration.review import run_review

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run = run_review(
        variant=args.variant,
        store=LocalArtifactStore(Path(args.out)),
        notifier=LogNotifier(),
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
        print("      rule floor only: relational (DF-7) and resilience (DF-5) findings need")
        print("      the LLM advisor, so they are not reported in this run")
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
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    result: int = args.func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
