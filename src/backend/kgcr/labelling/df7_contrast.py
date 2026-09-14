"""The empirical DF-7 gate: graph recovers the path, Checkov does not.

For each DF-7 estate this measures two facts on the *same* estate (FD-05 §7):

* **(a) graph-visible** — :func:`relational_path_exists` recovers the injected
  path within the hop bound.
* **(b) engine-blind** — Checkov's verdict *for the sink resource* is identical
  between the clean parent and the DF-7 estate. The sink is pre-existing and
  unmutated, so any change would be Checkov reacting to the injected reachability
  — and it does not.

Comparing the sink (not the whole estate) is deliberate: the injection adds
resources (a hop host, roles) that pick up Checkov's ordinary per-resource nits,
which have nothing to do with the relational defect. Those land on the added
resources, never on the sink, so the sink comparison is clean by construction.

The labeller is injectable so the contrast logic is testable with a stub — a
live Checkov run is slow and version-fragile and is reserved for producing the
evidence artifact.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.defects.detectors import relational_path_exists
from kgcr.defects.inject import applicable_injectors
from kgcr.defects.taxonomy import DefectClass
from kgcr.labelling.checkov_engine import CheckovFinding, resource_verdict, run_checkov

__all__ = ["Df7Contrast", "Df7VisibilityReport", "evaluate_df7_visibility", "HOP_BOUND"]

HOP_BOUND = 3

Labeller = Callable[[Estate], list[CheckovFinding]]


@dataclass(frozen=True, slots=True)
class Df7Contrast:
    """The (a) graph-visible / (b) engine-blind result for one DF-7 estate."""

    variant: str
    defect_estate_id: str
    parent_estate_id: str
    sink: str
    graph_recovers: bool
    checkov_sink_unchanged: bool
    sink_checks_added: tuple[str, ...]
    sink_checks_removed: tuple[str, ...]

    @property
    def c1_holds(self) -> bool:
        """The graph sees the defect and the engine does not."""
        return self.graph_recovers and self.checkov_sink_unchanged

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "defect_estate_id": self.defect_estate_id,
            "parent_estate_id": self.parent_estate_id,
            "sink": self.sink,
            "graph_recovers": self.graph_recovers,
            "checkov_sink_unchanged": self.checkov_sink_unchanged,
            "sink_checks_added": list(self.sink_checks_added),
            "sink_checks_removed": list(self.sink_checks_removed),
            "c1_holds": self.c1_holds,
        }


@dataclass(frozen=True, slots=True)
class Df7VisibilityReport:
    """Aggregate of the DF-7 contrast over a corpus."""

    contrasts: tuple[Df7Contrast, ...]

    @property
    def total(self) -> int:
        return len(self.contrasts)

    @property
    def graph_recovered(self) -> int:
        return sum(1 for c in self.contrasts if c.graph_recovers)

    @property
    def engine_blind(self) -> int:
        return sum(1 for c in self.contrasts if c.checkov_sink_unchanged)

    @property
    def c1_holds_for_all(self) -> bool:
        return self.total > 0 and all(c.c1_holds for c in self.contrasts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_df7_estates": self.total,
            "graph_recovered": self.graph_recovered,
            "engine_blind": self.engine_blind,
            "c1_holds_for_all": self.c1_holds_for_all,
            "by_variant": self._by_variant(),
            "contrasts": [c.to_dict() for c in self.contrasts],
        }

    def _by_variant(self) -> dict[str, dict[str, int]]:
        variants: dict[str, dict[str, int]] = {}
        for c in self.contrasts:
            v = variants.setdefault(
                c.variant, {"total": 0, "engine_blind": 0, "graph_recovered": 0}
            )
            v["total"] += 1
            v["engine_blind"] += int(c.checkov_sink_unchanged)
            v["graph_recovered"] += int(c.graph_recovers)
        return variants


def evaluate_df7_visibility(
    clean_estates: Sequence[Estate],
    labeller: Labeller = run_checkov,
) -> Df7VisibilityReport:
    """Run the DF-7 contrast over ``clean_estates`` using ``labeller``.

    Runs the labeller once per clean parent and once per injected DF-7 estate.
    With the default Checkov labeller this is slow; pass a stub for tests.
    """
    contrasts: list[Df7Contrast] = []
    for clean in clean_estates:
        df7_injectors = [
            inj for inj in applicable_injectors(clean) if inj.defect_class is DefectClass.RELATIONAL
        ]
        if not df7_injectors:
            continue
        parent_findings = labeller(clean)
        for injector in df7_injectors:
            result = injector.run(clean)
            sink = result.defect.evidence_path[-1]
            parent_sink = resource_verdict(parent_findings, sink)
            defect_sink = resource_verdict(labeller(result.estate), sink)

            path = relational_path_exists(
                result.estate,
                result.defect.evidence_path[0],
                sink,
                hop_bound=HOP_BOUND,
            )
            contrasts.append(
                Df7Contrast(
                    variant=injector.variant,
                    defect_estate_id=result.estate.estate_id,
                    parent_estate_id=clean.estate_id,
                    sink=sink,
                    graph_recovers=path is not None,
                    checkov_sink_unchanged=defect_sink == parent_sink,
                    sink_checks_added=tuple(sorted(c for c, _ in defect_sink - parent_sink)),
                    sink_checks_removed=tuple(sorted(c for c, _ in parent_sink - defect_sink)),
                )
            )
    return Df7VisibilityReport(contrasts=tuple(contrasts))
