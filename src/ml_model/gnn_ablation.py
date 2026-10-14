"""Does a graph neural network rank configuration options better than the random forest?

The recommender ranks options from intent alone. The GNN here gets what a graph can add: the
resource types as nodes, an edge wherever one type references another in the training estates,
and the intent as every node's input. Two layers of message passing lets an option of one type
see its neighbours' state. The same network with the edges removed is the control: if it does
as well, message passing is not what helped. Needs the ``gnn`` extra (torch); not part of CI.

    python src/ml_model/gnn_ablation.py --seeds 5 --corpus-seeds 1729 11 22 33

The expectation, stated before any run: no gain. The generator is a deterministic function of
intent and the forest already scores 1.000 R-precision on the held-out split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from kgcr.corpus.estate import Estate
from kgcr.corpus.pipeline import generate_corpus
from kgcr.corpus.splits import split_estates
from kgcr.defects.pipeline import inject_corpus
from kgcr.recommender.evaluate import _metrics
from kgcr.recommender.recommender import INTENT_FIELDS, OptionRecommender, estate_options
from kgcr.repro import DEFAULT_SEED, seed_everything

DEFAULT_REPORT = Path("results/gnn_ablation.json")
Option = tuple[str, str, str]


def _train_and_score(
    *,
    adjacency: np.ndarray,
    node_types: list[str],
    pool: list[Option],
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    epochs: int,
) -> np.ndarray:
    import torch
    from torch import nn

    torch.manual_seed(seed)
    n_nodes, hidden = len(node_types), 32
    a_hat = torch.tensor(adjacency, dtype=torch.float32)
    node_of = torch.tensor([node_types.index(o[0]) for o in pool])

    class TypeGraphNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.type_embedding = nn.Embedding(n_nodes, 16)
            self.inp = nn.Linear(x_fit.shape[1] + 16, hidden)
            self.layers = nn.ModuleList([nn.Linear(hidden, hidden), nn.Linear(hidden, hidden)])
            self.option_vec = nn.Parameter(torch.randn(len(pool), hidden) * 0.1)
            self.option_bias = nn.Parameter(torch.zeros(len(pool)))

        def forward(self, intent: torch.Tensor) -> torch.Tensor:
            batch = intent.shape[0]
            emb = self.type_embedding.weight.unsqueeze(0).expand(batch, -1, -1)
            context = intent.unsqueeze(1).expand(-1, n_nodes, -1)
            h = torch.relu(self.inp(torch.cat([context, emb], -1)))
            for layer in self.layers:
                h = torch.relu(layer(torch.matmul(a_hat, h)))
            per_option = h[:, node_of, :]  # (batch, options, hidden): the node each option sits on
            return (per_option * self.option_vec).sum(-1) + self.option_bias

    net = TypeGraphNet()
    optimiser = torch.optim.Adam(net.parameters(), lr=1e-2)
    xf = torch.tensor(x_fit, dtype=torch.float32)
    yf = torch.tensor(y_fit, dtype=torch.float32)
    for _ in range(epochs):
        optimiser.zero_grad()
        loss = nn.functional.binary_cross_entropy_with_logits(net(xf), yf)
        loss.backward()
        optimiser.step()
    with torch.no_grad():
        return torch.sigmoid(net(torch.tensor(x_test, dtype=torch.float32))).numpy()


def _normalised(edges: set[tuple[int, int]], n: int, *, connected: bool) -> np.ndarray:
    a = np.eye(n)
    if connected:
        for i, j in edges:
            a[i, j] = a[j, i] = 1.0
    degree = a.sum(1)
    return a / np.sqrt(np.outer(degree, degree))


def _one_corpus(count: int, corpus_seed: int, seeds: int, epochs: int) -> dict[str, Any]:
    seed_everything(corpus_seed)
    estates = generate_corpus(count, corpus_seed)
    split = split_estates(estates)
    by_id = {e.estate_id: e for e in estates}
    fit = [by_id[i] for i in (*split.train.estate_ids, *split.validation.estate_ids)]
    test = [by_id[i] for i in split.test.estate_ids]

    forest = OptionRecommender(random_state=0)
    forest.fit(fit, [d.estate for d in inject_corpus(fit)])
    pool = [o for o in forest.candidates if not forest.is_masked(o)]

    categories = {f: sorted({e.intent.to_dict()[f] for e in fit}) for f in INTENT_FIELDS}

    def encode(estate: Estate) -> list[float]:
        intent = estate.intent.to_dict()
        return [1.0 if intent[f] == c else 0.0 for f in INTENT_FIELDS for c in categories[f]]

    x_fit, x_test = np.array([encode(e) for e in fit]), np.array([encode(e) for e in test])
    y_fit = np.array([[o in estate_options(e) for o in pool] for e in fit], dtype=float)

    node_types = sorted({o[0] for o in pool})
    edges = {
        (node_types.index(r.type), node_types.index(ref.split(".")[0]))
        for e in fit
        for r in e.resources
        for ref in r.references
        if r.type in node_types and ref.split(".")[0] in node_types
    }

    def forest_scorer(estate: Estate) -> dict[Option, float]:
        return {r.option: r.score for r in forest.recommend(estate.intent.to_dict())}

    report: dict[str, Any] = {
        "corpus_seed": corpus_seed,
        "n_fit": len(fit),
        "n_test": len(test),
        "n_options": len(pool),
        "n_type_nodes": len(node_types),
        "n_type_edges": len(edges),
        "random_forest": _metrics(pool, test, forest_scorer),
    }
    for name, connected in (("gnn", True), ("same_network_without_edges", False)):
        adjacency = _normalised(edges, len(node_types), connected=connected)
        runs = []
        for seed in range(seeds):
            scores = _train_and_score(
                adjacency=adjacency,
                node_types=node_types,
                pool=pool,
                x_fit=x_fit,
                y_fit=y_fit,
                x_test=x_test,
                seed=seed,
                epochs=epochs,
            )
            by_estate = {
                e.estate_id: dict(zip(pool, scores[i], strict=True)) for i, e in enumerate(test)
            }
            runs.append(_metrics(pool, test, lambda e, table=by_estate: table[e.estate_id]))
        report[name] = {
            metric: {
                "mean": round(float(np.mean([r[metric] for r in runs])), 4),
                "min": round(float(np.min([r[metric] for r in runs])), 4),
                "max": round(float(np.max([r[metric] for r in runs])), 4),
            }
            for metric in runs[0]
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180)
    parser.add_argument("--corpus-seeds", type=int, nargs="+", default=[DEFAULT_SEED, 11, 22, 33])
    parser.add_argument("--seeds", type=int, default=5, help="Training seeds per variant")
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    corpora = []
    for corpus_seed in args.corpus_seeds:
        one = _one_corpus(args.count, corpus_seed, args.seeds, args.epochs)
        corpora.append(one)
        print(
            f"corpus seed {corpus_seed}: forest exact_set {one['random_forest']['exact_set']}, "
            f"gnn {one['gnn']['exact_set']['mean']}, "
            f"without edges {one['same_network_without_edges']['exact_set']['mean']}",
            flush=True,
        )

    def pooled(get: Any) -> float:
        return round(float(np.mean([get(c) for c in corpora])), 4)

    report: dict[str, Any] = {
        "question": "does message passing over the resource-type graph beat the random forest?",
        "expectation_before_running": "no gain",
        "training_seeds_per_corpus": args.seeds,
        "epochs": args.epochs,
        "test_estates_in_all": sum(c["n_test"] for c in corpora),
        "exact_set_pooled_over_corpora": {
            "random_forest": pooled(lambda c: c["random_forest"]["exact_set"]),
            "gnn": pooled(lambda c: c["gnn"]["exact_set"]["mean"]),
            "same_network_without_edges": pooled(
                lambda c: c["same_network_without_edges"]["exact_set"]["mean"]
            ),
        },
        "corpora": corpora,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.report_out.write_text(text, encoding="utf-8")
    print(report["exact_set_pooled_over_corpora"])
    print(f"report: {args.report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
