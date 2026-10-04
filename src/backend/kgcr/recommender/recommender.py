"""Candidate spec synthesis (FD-01 S2): retrieve, rank, then mask.

An *option* is one configuration choice, ``(resource_type, attribute, value)``,
with ``("aws_cloudtrail", "present", "true")`` standing for "include a trail".
Identity attributes (names, tags, CIDRs, references) are excluded: they name a
resource rather than configure it, and keeping them would let a model memorise
injected addresses such as ``df7_public_hop``.

1. **Retrieve** — the candidate pool is every option seen in the clean corpus
   *and* the defect corpus, so non-compliant alternatives are genuinely on offer.
2. **Rank** — one RandomForest per option (one-vs-rest) scores it from the intent.
   A single joint multi-output forest was tried first and lost exact-set recovery
   (0.875 vs 0.958) because shared splits dilute rare options such as large
   instance types.
3. **Mask** — each option is applied to a compliant template resource of its type
   and re-checked with the single-resource rules; any CRITICAL finding removes it.
   The mask is a filter on the output, never a training objective (FD-01 S2): a
   model that learned to avoid an illegal option can still emit one; a filter
   cannot.

ponytail: this is not the roadmap's GNN. The synthetic generator is a
deterministic function of intent, and a RandomForest on intent already scores
0.958 exact-set recovery and 1.000 R-precision on the held-out split
(results/recommender_report.json),
so a GNN has no headroom to show. Revisit when the corpus carries options that
depend on graph structure rather than intent alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier

from kgcr.corpus.estate import Estate
from kgcr.corpus.resources import Resource
from kgcr.defects.detectors import Finding, resource_findings
from kgcr.defects.taxonomy import DEFAULT_SEVERITY, Severity
from kgcr.reconstruction.reconstructor import RECONSTRUCTED_FIELDS, ReconstructedIntent

__all__ = [
    "Option",
    "RankedOption",
    "INTENT_FIELDS",
    "estate_options",
    "intent_from_reconstruction",
    "OptionRecommender",
]

Option = tuple[str, str, str]

# Region is an input too: availability-zone values are region-specific.
INTENT_FIELDS: tuple[str, ...] = (*RECONSTRUCTED_FIELDS, "region")

_IDENTITY_ATTRIBUTES = frozenset(
    {"name", "identifier", "bucket", "description", "tags", "cidr_block", "function_name"}
)


@dataclass(frozen=True, slots=True)
class RankedOption:
    """One option and its score in [0, 1]."""

    option: Option
    score: float


def _option_values(estate: Estate) -> Iterable[tuple[Option, Any]]:
    """Each option in ``estate`` with the raw attribute value behind it."""
    for res in estate.resources:
        yield (res.type, "present", "true"), True
        for key, value in res.attributes.items():
            # Nested values (ingress blocks, policy documents) are not scalar
            # choices; DF-1/DF-3 live there and are covered by the advisor.
            if key in _IDENTITY_ATTRIBUTES or key.startswith("__ref__"):
                continue
            if isinstance(value, dict | list) or key in {"policy", "assume_role_policy"}:
                continue
            yield (res.type, key, str(value)), value


def estate_options(estate: Estate) -> frozenset[Option]:
    """The configuration options an estate exhibits."""
    return frozenset(option for option, _ in _option_values(estate))


def intent_from_reconstruction(reconstructed: ReconstructedIntent) -> dict[str, str]:
    """Flatten a P8 reconstruction into the ``{field: value}`` the ranker takes."""
    return {
        "region": reconstructed.region,
        **{f: reconstructed.value(f) for f in RECONSTRUCTED_FIELDS},
    }


class OptionRecommender:
    """Retrieve, rank and mask configuration options for an intent."""

    def __init__(self, random_state: int = 0) -> None:
        self._random_state = random_state
        self._model: Any = None  # sklearn ships no stubs
        self._categories: dict[str, list[str]] = {}
        self.candidates: tuple[Option, ...] = ()
        self._findings: dict[Option, tuple[Finding, ...]] = {}

    def fit(self, clean: Sequence[Estate], defected: Sequence[Estate]) -> None:
        """Learn option relevance from ``clean``; retrieve candidates from both."""
        if not clean:
            raise ValueError("cannot fit the recommender on an empty corpus")
        raw: dict[Option, Any] = {}
        templates: dict[str, Resource] = {}
        for estate in (*clean, *defected):
            for option, value in _option_values(estate):
                raw.setdefault(option, value)
            for res in estate.resources:
                # A finding-free resource is a compliant context to test options in.
                if res.type not in templates and not resource_findings(res):
                    templates[res.type] = res
        self.candidates = tuple(sorted(raw))
        self._findings = {
            option: self._option_findings(option, raw[option], templates)
            for option in self.candidates
        }

        self._categories = {
            f: sorted({e.intent.to_dict()[f] for e in clean}) for f in INTENT_FIELDS
        }
        x = np.array([self._encode(e.intent.to_dict()) for e in clean])
        y = np.array([[o in estate_options(e) for o in self.candidates] for e in clean], dtype=int)
        self._model = MultiOutputClassifier(
            RandomForestClassifier(n_estimators=100, random_state=self._random_state)
        )
        self._model.fit(x, y)

    @staticmethod
    def _option_findings(
        option: Option, value: Any, templates: Mapping[str, Resource]
    ) -> tuple[Finding, ...]:
        res_type, attribute, _ = option
        template = templates.get(res_type)
        if template is None:
            raise ValueError(f"no compliant template for {res_type}; cannot evaluate {option}")
        if attribute == "present":
            return ()
        trial = replace(template, attributes={**template.attributes, attribute: value})
        return tuple(resource_findings(trial))

    def _encode(self, intent: Mapping[str, str]) -> list[float]:
        missing = [f for f in INTENT_FIELDS if f not in intent]
        if missing:
            raise ValueError(f"intent is missing fields: {missing}")
        # An unseen value encodes as all-zero for its field rather than failing.
        return [1.0 if intent[f] == c else 0.0 for f in INTENT_FIELDS for c in self._categories[f]]

    def option_findings(self, option: Option) -> tuple[Finding, ...]:
        """Single-resource findings the option introduces in a compliant context."""
        return self._findings[option]

    def is_masked(self, option: Option) -> bool:
        """True if the option introduces a CRITICAL finding."""
        return any(
            DEFAULT_SEVERITY[f.defect_class] is Severity.CRITICAL for f in self._findings[option]
        )

    def score(self, intent: Mapping[str, str]) -> list[RankedOption]:
        """Rank every candidate, unmasked, highest score first."""
        if self._model is None:
            raise RuntimeError("recommender is not fitted")
        probabilities = self._model.predict_proba(np.array([self._encode(intent)]))
        ranked: list[RankedOption] = []
        for option, proba, classes in zip(
            self.candidates,
            probabilities,
            [est.classes_ for est in self._model.estimators_],
            strict=True,
        ):
            labels = [int(c) for c in classes]
            p = float(proba[0][labels.index(1)]) if 1 in labels else 0.0
            ranked.append(RankedOption(option, p))
        return sorted(ranked, key=lambda r: (-r.score, r.option))

    def apply_mask(self, ranked: Sequence[RankedOption]) -> list[RankedOption]:
        """Drop CRITICAL-violating options, preserving order."""
        return [r for r in ranked if not self.is_masked(r.option)]

    def recommend(self, intent: Mapping[str, str]) -> list[RankedOption]:
        """Rank, then mask: the only output path callers should use."""
        return self.apply_mask(self.score(intent))
