"""Inject defects across a clean corpus and write the ground-truth manifest.

The engine pairs every clean estate with each defect its shape admits, so one
clean corpus yields many defect estates — each carrying exactly one seeded
defect with full ground truth (FD-04 §10). DF-7 is produced *in quantity* this
way: every estate contributes its applicable relational variants, not a handful
of exemplars.

:func:`verify_df7_gate` is the runnable form of the P5 soft gate. It checks the
*by-construction invariant*: every DF-7 estate carries **zero** single-resource
findings (the oracle of :mod:`kgcr.defects.detectors`), yet a graph traversal
recovers its evidence path. The empirical "real engines score zero" check is the
Phase 4 labelling pipeline's job (FD-05 §6); this proves the property the
corpus was built to have.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.corpus.graph import build_graph_from_estate
from kgcr.defects.detectors import relational_path_exists, single_resource_findings
from kgcr.defects.inject import DefectedEstate, applicable_injectors
from kgcr.defects.taxonomy import DefectClass

__all__ = [
    "inject_corpus",
    "df7_set",
    "summarise_defects",
    "verify_df7_gate",
    "write_defect_corpus",
    "GateReport",
    "HOP_BOUND",
]

# The relational-predicate hop bound k (FD-07 §7, D9). DF-7 paths are built to
# sit within it; the gate checks recovery within it.
HOP_BOUND = 3


def inject_corpus(clean_estates: Sequence[Estate]) -> list[DefectedEstate]:
    """Inject every applicable defect into every clean estate.

    Deterministic in the input corpus: each defect estate's id derives from its
    parent id and the variant, so the same clean corpus always yields the same
    defect corpus.
    """
    defected: list[DefectedEstate] = []
    for estate in clean_estates:
        for injector in applicable_injectors(estate):
            defected.append(injector.run(estate))
    return defected


def df7_set(defected: Sequence[DefectedEstate]) -> list[DefectedEstate]:
    """The relational (DF-7) subset — the FD-05 §9 Relational split."""
    return [d for d in defected if d.defect.defect_class is DefectClass.RELATIONAL]


@dataclass(frozen=True, slots=True)
class GateReport:
    """Result of the DF-7 by-construction invariant check."""

    df7_estates: int
    single_resource_clean: bool
    paths_recovered: bool
    single_resource_offenders: tuple[str, ...]
    unrecovered_paths: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.single_resource_clean and self.paths_recovered

    def to_dict(self) -> dict[str, Any]:
        return {
            "df7_estates": self.df7_estates,
            "single_resource_clean": self.single_resource_clean,
            "paths_recovered": self.paths_recovered,
            "single_resource_offenders": list(self.single_resource_offenders),
            "unrecovered_paths": list(self.unrecovered_paths),
            "passed": self.passed,
        }


def verify_df7_gate(defected: Sequence[DefectedEstate]) -> GateReport:
    """Check the DF-7 invariant: single-resource-clean, graph-recoverable.

    For every DF-7 estate:

    * :func:`single_resource_findings` must return nothing — no resource on the
      path is individually non-compliant, which is why single-resource engines
      score zero on this set by construction.
    * :func:`relational_path_exists` must recover a path between the recorded
      evidence path's endpoints within :data:`HOP_BOUND` hops.
    """
    df7 = df7_set(defected)
    offenders: list[str] = []
    unrecovered: list[str] = []

    for item in df7:
        if single_resource_findings(item.estate):
            offenders.append(item.estate.estate_id)

        path = item.defect.evidence_path
        source, sink = path[0], path[-1]
        if relational_path_exists(item.estate, source, sink, hop_bound=HOP_BOUND) is None:
            unrecovered.append(item.estate.estate_id)

    return GateReport(
        df7_estates=len(df7),
        single_resource_clean=not offenders,
        paths_recovered=not unrecovered,
        single_resource_offenders=tuple(offenders),
        unrecovered_paths=tuple(unrecovered),
    )


def summarise_defects(defected: Sequence[DefectedEstate]) -> dict[str, Any]:
    """Aggregate counts: per class, per variant, per severity, hop distribution."""
    by_class: Counter[str] = Counter()
    by_variant: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    hop_counts: Counter[int] = Counter()

    for item in defected:
        d = item.defect
        by_class[d.defect_class.value] += 1
        by_variant[d.variant] += 1
        by_severity[d.severity.value] += 1
        if d.is_relational:
            hop_counts[d.hop_count] += 1

    return {
        "defects": len(defected),
        "df7_defects": sum(1 for d in defected if d.defect.is_relational),
        "classes_present": sorted(by_class),
        "by_class": dict(sorted(by_class.items())),
        "by_variant": dict(sorted(by_variant.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "df7_hop_distribution": {str(k): v for k, v in sorted(hop_counts.items())},
    }


def write_defect_corpus(defected: Sequence[DefectedEstate], out_dir: str | Path) -> dict[str, Any]:
    """Write per-defect artifacts and a manifest to ``out_dir``.

    Per defect estate, three files land under ``estates/``: the Terraform JSON,
    the dependency graph, and the ground-truth ``DefectInstance``. The manifest
    records the summary, the DF-7 gate report, the per-defect index, and the
    Relational split (the DF-7 estate ids).
    """
    out = Path(out_dir)
    estates_dir = out / "estates"
    estates_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict[str, Any]] = []
    for item in defected:
        estate, defect = item.estate, item.defect
        base = estates_dir / estate.estate_id
        _write_json(base.with_suffix(".tf.json"), estate.to_terraform_json())
        _write_json(base.with_suffix(".graph.json"), build_graph_from_estate(estate).to_dict())
        _write_json(base.with_suffix(".defect.json"), defect.to_dict())
        index.append(
            {
                "estate_id": estate.estate_id,
                "parent_estate_id": defect.parent_estate_id,
                "seed_family": defect.seed_family,
                "defect_class": defect.defect_class.value,
                "variant": defect.variant,
                "control": defect.control,
                "severity": defect.severity.value,
                "hop_count": defect.hop_count,
            }
        )

    manifest: dict[str, Any] = {
        "summary": summarise_defects(defected),
        "df7_gate": verify_df7_gate(defected).to_dict(),
        "relational_split": [d.estate.estate_id for d in df7_set(defected)],
        "defects": index,
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
