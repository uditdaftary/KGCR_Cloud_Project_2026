"""Candidate spec synthesis for design mode (FD-01 S2).

The topology comes from the generator, because in this corpus the topology is a function
of the intent. The fitted recommender then ranks and masks options for the same intent and
audits the skeleton against them:

* a recommended option the skeleton lacks, on a resource type the skeleton has exactly one
  of, is applied as an attribute patch;
* any other gap, and any option the skeleton has that the recommender does not want, is
  reported and left alone (adding a resource needs references an option does not carry);
* a skeleton that contains an option the CRITICAL mask removes is a bug and fails loudly.

On this synthetic corpus the recommender recovers the generator's own mapping, so the two
agree almost by construction. The result shows the pipeline and its guarantees. It is not
independent evidence of recommendation quality.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kgcr.corpus.estate import Estate
from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import Intent
from kgcr.recommender.recommender import (
    INTENT_FIELDS,
    Option,
    OptionRecommender,
    RankedOption,
    estate_options,
)

__all__ = ["CHOSEN_SCORE", "Candidate", "MaskViolation", "intent_values", "synthesize"]

CHOSEN_SCORE = 0.5  # the same cut the review pipeline uses for "recommended"


class MaskViolation(RuntimeError):
    """The skeleton holds an option the CRITICAL mask would remove (INV-1)."""


@dataclass(frozen=True, slots=True)
class Candidate:
    estate: Estate
    applied: tuple[Option, ...]
    reported_missing: tuple[Option, ...]
    reported_unexpected: tuple[Option, ...]
    recommended: tuple[RankedOption, ...]


def intent_values(intent: Intent) -> dict[str, str]:
    """The ``{field: value}`` the ranker and the advisor take (no derived fields)."""
    full = intent.to_dict()
    return {f: full[f] for f in INTENT_FIELDS}


def synthesize(intent: Intent, seed: int, recommender: OptionRecommender) -> Candidate:
    skeleton = render_estate(intent, seed)
    known = set(recommender.candidates)
    masked = sorted(o for o in estate_options(skeleton) if o in known and recommender.is_masked(o))
    if masked:
        raise MaskViolation(f"skeleton for {skeleton.estate_id} holds masked options: {masked}")

    ranked = tuple(recommender.recommend(intent_values(intent)))
    wanted = {r.option for r in ranked if r.score >= CHOSEN_SCORE}
    observed = estate_options(skeleton)

    resources = list(skeleton.resources)
    applied: list[Option] = []
    reported: list[Option] = []
    for option in sorted(wanted - observed):
        res_type, attribute, _ = option
        same_type = [i for i, r in enumerate(resources) if r.type == res_type]
        if attribute == "present" or len(same_type) != 1 or option not in recommender.raw_values:
            reported.append(option)
            continue
        i = same_type[0]
        resources[i] = replace(
            resources[i],
            attributes={**resources[i].attributes, attribute: recommender.raw_values[option]},
        )
        applied.append(option)

    estate = replace(skeleton, resources=tuple(resources))
    return Candidate(
        estate=estate,
        applied=tuple(applied),
        reported_missing=tuple(reported),
        reported_unexpected=tuple(sorted(observed - wanted)),
        recommended=ranked,
    )
