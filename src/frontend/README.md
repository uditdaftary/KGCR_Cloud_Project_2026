# Frontend

`build_dashboard.py` builds `results/dashboard.html`, a static, offline view over `results/*.json`:
gate status, seeded-defect recall, reconstruction calibration, the recommender against its
baselines, and the latest `kgcr review` run.

```
python src/frontend/build_dashboard.py
```

The page reads gate state from the reports, so rebuild it after `run_advisor.py`.

## Phase-II scope

An interactive web UI is not part of Phase-I; the Phase-I interface is the `kgcr` CLI (see
[../backend/kgcr/cli.py](../backend/kgcr/cli.py)). Planned for Phase-II: the DF-7 contrast evidence
and the per-field reliability diagram served alongside the review output, with the audience modes
(`architect` / `auditor` / `learner`) that FD-06 specifies.
