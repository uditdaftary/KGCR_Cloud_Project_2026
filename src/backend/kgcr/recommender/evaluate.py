"""The P7 experiment: rankers versus baselines on the held-out split (roadmap P7 gate).

Relevance for a test estate is the option set its clean estate exhibits. Every
ranker is scored over the same masked candidate pool, with:

* ``ndcg`` — full-list NDCG;
* ``p_at_10`` — precision in the top 10 (saturates here: ~18 of ~34 options are
  relevant per estate, so it is reported but carries little signal);
* ``r_precision`` — precision in the top ``|relevant|``;
* ``exact_set`` — fraction of estates whose ``score >= 0.5`` set equals the
  relevant set exactly. This is the discriminating metric on this corpus.

The model is evaluated twice: on the true intent, and on the P8-reconstructed
intent, which is what the end-to-end demo actually feeds it.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import ndcg_score

from kgcr.corpus.estate import Estate
from kgcr.corpus.splits import check_split_integrity, split_estates
from kgcr.defects.pipeline import inject_corpus
from kgcr.recommender.recommender import (
    OptionRecommender,
    estate_options,
    intent_from_reconstruction,
)
from kgcr.reconstruction.reconstructor import IntentReconstructor

__all__ = ["RecommenderExperiment", "run_recommender_experiment", "write_report"]

_Scorer = Callable[[Estate], dict[tuple[str, str, str], float]]


@dataclass(frozen=True, slots=True)
class RecommenderExperiment:
    """The fitted recommender and its JSON-ready report."""

    recommender: OptionRecommender
    report: dict[str, Any]


def _metrics(
    pool: Sequence[tuple[str, str, str]], test: Sequence[Estate], scorer: _Scorer
) -> dict[str, float]:
    truth = np.array([[o in estate_options(e) for o in pool] for e in test], dtype=float)
    scored = [scorer(e) for e in test]
    scores = np.array([[s.get(o, 0.0) for o in pool] for s in scored])
    p_at_10: list[float] = []
    r_prec: list[float] = []
    exact: list[bool] = []
    for i, estate in enumerate(test):
        order = np.argsort(-scores[i], kind="stable")
        relevant = len(estate_options(estate))
        p_at_10.append(float(truth[i][order[:10]].mean()))
        r_prec.append(float(truth[i][order[:relevant]].sum()) / relevant)
        predicted = {pool[j] for j in range(len(pool)) if scores[i][j] >= 0.5}
        exact.append(predicted == estate_options(estate))
    return {
        "ndcg": round(float(ndcg_score(truth, scores)), 4),
        "p_at_10": round(float(np.mean(p_at_10)), 4),
        "r_precision": round(float(np.mean(r_prec)), 4),
        "exact_set": round(float(np.mean(exact)), 4),
    }


def run_recommender_experiment(
    estates: Sequence[Estate], *, random_state: int = 0
) -> RecommenderExperiment:
    """Fit on train+validation (plus its defect corpus); evaluate on test."""
    split = split_estates(estates)
    check_split_integrity(estates, split)
    by_id = {e.estate_id: e for e in estates}
    fit = [by_id[i] for i in (*split.train.estate_ids, *split.validation.estate_ids)]
    test = [by_id[i] for i in split.test.estate_ids]
    if not fit or not test:
        raise ValueError("split produced an empty train or test set; supply more estates")

    # Defects come from the fit side only, so test estates never shape retrieval.
    defected = [d.estate for d in inject_corpus(fit)]
    recommender = OptionRecommender(random_state=random_state)
    recommender.fit(fit, defected)
    pool = [o for o in recommender.candidates if not recommender.is_masked(o)]

    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    by_archetype: dict[str, list[Estate]] = defaultdict(list)
    for estate in fit:
        by_archetype[estate.intent.archetype.value].append(estate)
        for option in estate_options(estate):
            counts[option] += 1
    popularity = {o: n / len(fit) for o, n in counts.items()}

    frequency = {
        archetype: {o: sum(o in estate_options(g) for g in group) / len(group) for o in pool}
        for archetype, group in by_archetype.items()
    }

    def archetype_frequency(estate: Estate) -> dict[tuple[str, str, str], float]:
        return frequency.get(estate.intent.archetype.value, popularity)

    reconstructor = IntentReconstructor(random_state=random_state)
    reconstructor.fit(fit)

    def model_on(intent_of: Callable[[Estate], dict[str, str]]) -> _Scorer:
        return lambda e: {r.option: r.score for r in recommender.recommend(intent_of(e))}

    rankers: dict[str, _Scorer] = {
        "popularity": lambda _e: popularity,
        "archetype_frequency": archetype_frequency,
        "model_true_intent": model_on(lambda e: e.intent.to_dict()),
        "model_reconstructed_intent": model_on(
            lambda e: intent_from_reconstruction(reconstructor.reconstruct(e))
        ),
    }
    masked = [o for o in recommender.candidates if recommender.is_masked(o)]
    flagged = [
        o for o in recommender.candidates if recommender.option_findings(o) and o not in masked
    ]
    report: dict[str, Any] = {
        "corpus": "synthetic, self-generated (kgcr.corpus)",
        "model": "one-vs-rest RandomForestClassifier per option on one-hot intent",
        "n_estates": len(estates),
        "n_fit": len(fit),
        "n_test": len(test),
        "n_candidates": len(recommender.candidates),
        "n_pool_after_mask": len(pool),
        "masked_critical": [list(o) for o in masked],
        "flagged_noncritical": [list(o) for o in flagged],
        "rankers": {name: _metrics(pool, test, scorer) for name, scorer in rankers.items()},
    }
    return RecommenderExperiment(recommender, report)


def write_report(experiment: RecommenderExperiment, path: str | Path) -> Path:
    """Write the report as stable JSON, returning the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(experiment.report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
