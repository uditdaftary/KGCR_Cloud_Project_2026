"""Corpus A generation pipeline: sample → render → graph → manifest.

Ties the pieces into the Phase 3 gate deliverable — *N estates generated and
parsed into the graph* (roadmap P3). Generation is organised into *seed
families*: a family shares one sampled intent and differs only by render jitter,
producing the structurally near-identical estates that the estate-level split
(FD-05 §9) must keep together.

Render seeds are drawn from a monotonic counter mixed with the base seed, so
every estate in a run gets a unique seed — hence a unique ``estate_id`` — and
the whole run reproduces exactly from ``(count, seed, family_size)``.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.corpus.generator import render_estate
from kgcr.corpus.graph import build_graph_from_estate
from kgcr.corpus.sampler import IntentSampler
from kgcr.corpus.splits import CorpusSplit, check_split_integrity, split_estates
from kgcr.repro import DEFAULT_SEED

__all__ = ["generate_corpus", "summarise_corpus", "write_corpus"]


def _render_seed(base_seed: int, counter: int) -> int:
    # Disjoint high ranges per base seed keep render seeds unique across a run
    # and reproducible.
    return 10_000_000 * (base_seed + 1) + counter


def generate_corpus(
    count: int,
    seed: int = DEFAULT_SEED,
    *,
    family_size: int = 1,
) -> list[Estate]:
    """Generate ``count`` estates, grouped into families of ``family_size``.

    With ``family_size == 1`` every estate is its own family (the default, used
    for the gate count). Larger families exercise the leakage guard: same intent,
    different jitter, guaranteed to share a split.
    """
    if count < 0:
        raise ValueError(f"count must be non-negative, got {count}")
    if family_size < 1:
        raise ValueError(f"family_size must be >= 1, got {family_size}")

    sampler = IntentSampler(seed)
    estates: list[Estate] = []
    counter = 0
    family_index = 0

    while len(estates) < count:
        intent = sampler.sample()
        family_id = f"fam-{seed}-{family_index}"
        family_index += 1
        for _ in range(family_size):
            if len(estates) >= count:
                break
            estate = render_estate(intent, _render_seed(seed, counter), seed_family=family_id)
            counter += 1
            estates.append(estate)

    return estates


def summarise_corpus(estates: Sequence[Estate]) -> dict[str, Any]:
    """Aggregate counts over a corpus, including graph totals.

    Building every graph here doubles as the "parsed into the graph" half of the
    gate: it fails loudly if any estate produces a graph with dangling edges.
    """
    archetypes: Counter[str] = Counter()
    families: set[str] = set()
    total_resources = 0
    total_nodes = 0
    total_edges = 0

    for estate in estates:
        archetypes[estate.intent.archetype.value] += 1
        families.add(estate.seed_family)
        total_resources += len(estate.resources)
        graph = build_graph_from_estate(estate)
        graph.validate()
        total_nodes += graph.node_count
        total_edges += graph.edge_count

    return {
        "estates": len(estates),
        "seed_families": len(families),
        "archetypes": dict(sorted(archetypes.items())),
        "total_resources": total_resources,
        "total_graph_nodes": total_nodes,
        "total_graph_edges": total_edges,
        "unique_estate_ids": len({e.estate_id for e in estates}),
    }


def write_corpus(
    estates: Sequence[Estate],
    out_dir: str | Path,
    *,
    split: CorpusSplit | None = None,
) -> dict[str, Any]:
    """Write the corpus to ``out_dir`` and return its manifest.

    Per estate, three artifacts land under ``estates/``: the Terraform JSON, the
    ground-truth intent, and the dependency graph. A ``manifest.json`` records
    the summary, the per-estate index, and the split (computed if not supplied).
    """
    out = Path(out_dir)
    estates_dir = out / "estates"
    estates_dir.mkdir(parents=True, exist_ok=True)

    if split is None:
        split = split_estates(estates)
    check_split_integrity(estates, split)

    index: list[dict[str, str]] = []
    for estate in estates:
        base = estates_dir / estate.estate_id
        _write_json(base.with_suffix(".tf.json"), estate.to_terraform_json())
        _write_json(base.with_suffix(".intent.json"), estate.intent.to_dict())
        _write_json(base.with_suffix(".graph.json"), build_graph_from_estate(estate).to_dict())
        index.append(
            {
                "estate_id": estate.estate_id,
                "archetype": estate.intent.archetype.value,
                "seed_family": estate.seed_family,
            }
        )

    manifest: dict[str, Any] = {
        "summary": summarise_corpus(estates),
        "split": split.as_dict(),
        "estates": index,
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
