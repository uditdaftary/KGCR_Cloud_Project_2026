# Review 2 presentation — outline

**Project:** KGCR — Knowledge Graph-Based Cloud Configuration Recommendation
**Course:** BCSE355L, Dr. Priya V · **Team:** Udit (lead), Manya, Tanmoy

The deck is `KGCR_Review2.pptx`, built by `make_deck.js` (pptxgenjs). Every number on a slide is read
from a committed results file when the deck is built, so the deck cannot drift from the results. Each
slide's speaker notes name its source.

```bash
cd presentation && npm install
NODE_PATH="$PWD/node_modules" PPTX_SKILL_DIR=<pptx skill dir> node make_deck.js
```

`PPTX_SKILL_DIR` supplies the theme writer. Without it the deck still builds, with a warning, but
uses Office's default colours.

Fourteen slides, roughly 15 minutes plus questions.

| # | Slide | Source |
|---|---|---|
| 1 | Title | — |
| 2 | Per-resource checks miss defects in the connections (the DF-7 chain) | `docs/Project_Report.md` §1, FD-05 §5 |
| 3 | Fifteen papers agree on what is missing | `docs/Literature_Survey.md`, research-gap documents |
| 4 | Six objectives, each with a measure and a status | `docs/Objectives.md` |
| 5 | Diagram 1: AWS cloud architecture (planned) | `architecture/AWS_Architecture.png` |
| 6 | Diagram 2: complete system flow | `architecture/System_Architecture.png` |
| 7 | The dataset is synthetic, and generated intent-first | `dataset/dataset_description.md` |
| 8 | One command runs review mode end to end | `src/backend/kgcr/orchestration/` |
| 9 | Recommender result versus baselines | `results/recommender_report.json` |
| 10 | Advisor: rules catch properties, the graph catches paths; sycophancy gate status | `results/advisor_report.json`, `results/p4_df7_checkov_evidence.json` |
| 11 | Intent reconstruction per field; explainer INV-2 | `results/reconstruction_report.json`, `tests/explainer/` |
| 12 | Demo: a cardholder database without encryption | `kgcr review --variant unencrypted_database` |
| 13 | AWS services: planned versus running | `docs/Project_Report.md` §8 |
| 14 | Limits, and what comes next | `CHANGELOG.md` LOOP_STATE |

## Preparation notes

- Say "synthetic" on slide 7 before anyone asks.
- Slide 10: the sycophancy gate reads **Not run yet** until the live Gemini run is recorded. Do not
  describe the offline scripted-model test as the gate result.
- Slide 12 can be run live; `kgcr review` takes about 15 seconds.
- Each member explains their own five papers and their own commits. Code in this repository is
  Udit's, written with Claude's assistance.
