# Final review presentation: outline

**Project:** KGCR, Knowledge Graph-Based Cloud Configuration Recommendation
**Course:** BCSE355L, Dr. Priya V. **Team:** Udit (lead), Manya, Tanmoy

`KGCR_Final.pptx` is the final-review deck, written in the first person plural. It is built by
`make_deck.js` (pptxgenjs). `KGCR_Review2.pptx` is the earlier Review 2 deck, kept as it was and
never touched by the build.

```bash
cd presentation && npm install
NODE_PATH="$PWD/node_modules" PPTX_SKILL_DIR=<pptx skill dir> node make_deck.js
```

`PPTX_SKILL_DIR` supplies the theme writer. Without it the deck still builds, with a warning, but
uses Office's default colours. Every number on a results slide is read from a committed results
file when the deck is built, and the build refuses to run if the sycophancy gate stops reading
PASS. The speaker notes name each slide's source and carry the caveats the slides leave out.

## Slides (57)

| # | Slide | Source |
|---|---|---|
| 1 | Title | none |
| 2 to 4 | The defect scanners miss (DF-7), fifteen papers and the gap, six objectives with status | `docs/Project_Report.md`, `docs/Literature_Survey.md`, `docs/Objectives.md` |
| 5 | What we built, in numbers | `CHANGELOG.md`, `git log`, `docs/` |
| 6 to 8 | AWS architecture, system flow, AWS services (runs, written, planned) | `architecture/*.png`, `docs/Project_Report.md` section 8 |
| 9 to 10 | Synthetic dataset and Corpus D, the one-command pipeline | `dataset/dataset_description.md`, `results/corpus_d_report.json` |
| 11 to 15 | Graph versus Checkov, recommender, sycophancy gate, intent reconstruction, explainer | `results/*.json` |
| 16 to 17 | Outside validation, engineering and guardrails | `results/labeller_agreement.json`, `CHANGELOG.md` |
| 18 to 34 | Terminal: seventeen slides of empty frames for CLI screenshots | `CLI_RUNBOOK.md` |
| 35 to 55 | Dashboard tour: every page, 21 screenshots | `screenshots/tiles/` |
| 56 | Live demo (empty on purpose) | none |
| 57 | What we ship next | `CHANGELOG.md` |

## Screenshots

- `screenshots/*.png` are full-page captures of the live dashboard (1600 px wide at 1.5x), taken
  with headless Chrome against `python -m kgcr.cli dashboard`.
- `screenshots/tiles/*.png` are 2400x1350 crops of those pages; the deck embeds the tiles.
- The terminal frames are empty on purpose. `CLI_RUNBOOK.md` lists the commands in run order, with
  the expected output and the frame size for each.

## Preparation notes

- Say "synthetic" on slide 9 before anyone asks.
- Slide 13: the gate passed on 3 valid trials of 4 (one invalid). Beyond the rule floor the model
  found 2 of 4 variants and raised 1 false CRITICAL on 4 clean estates. The notes say so.
- Slide 8 is the planned-versus-running split; nothing has touched a real AWS account.
- Each member explains their own five papers and their own commits. Code in this repository is
  Udit's, written with Claude's assistance.
