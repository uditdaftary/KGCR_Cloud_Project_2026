# Phase-I realignment plan — KGCR → `KGCR_Cloud_Project_2026`

Source of truth: `Project Guidelines-AWS Cloud.pdf` (BCSE355L, Dr. Priya V, submission **30 July 2026**).
Written 2026-07-29.

---

## 1. What the evidence actually says

You called this "heavy refactoring." It isn't. The code move is a `git mv` plus four config lines.
The graded gap is **documents that do not exist yet, due tomorrow**.

| | Reality |
|---|---|
| Code restructuring | ~1 hour: move `kgcr/` under `src/backend/`, `environment/` under `src/aws/`, add 3 ML entry-point wrappers, re-run the gates. |
| Missing deliverables | 2 mandatory architecture diagrams, 15-paper literature survey, 3 research-gap documents, dataset details, AWS services table, abstract, objectives, novelty, presentation, LICENSE. |

So this plan is organised around the PDF's required-section list, not around file choreography.
Section 4 is the migration (small). Sections 5–7 are the actual work.

**Two corrections to the stated first action:**

1. **There is no `CLAUDE.md` in this repo.** `logs.md` is the de-facto one — "build log: processes
   and progress", phase status table, quality gates, decisions, gotchas, commit record. That is what
   goes into the new `CHANGELOG.md`. `README.md` is the public description and goes to the new
   `README.md`, not the changelog.
2. **"New repo" must not mean "empty repo."** 22 commits are the only evidence of GitHub activity
   you have, and commit history is explicitly graded. Create the correctly-named repo and **push the
   existing history into it**, then archive the old one. You get the mandated name, the history, and
   `KGCR` intact as reference-only.

---

## 2. Scope and assumptions

**Scope: Student 1 (team lead) only.** The team is three students, but everything planned here is
authored by and attributed to the lead. Students 2 and 3 get their branches created as scaffolding
and own their sections (their papers, their research-gap docs) themselves — nothing in this plan
writes for them or commits under their names.

| Assumption | Basis | Delta if wrong |
|---|---|---|
| Repo name `KGCR_Cloud_Project_2026` | PDF format `ProjectName_Cloud_Project_2026` | Rename is one click |
| Private repo, matching `KGCR` | Existing repo is private | Flip visibility, or add the instructor as a collaborator |
| AWS, not Azure | PDF is a lightly adapted Azure template (contribution matrix says "Azure Cloud Services", p.8 says "Azure/AWS"). Course code and title say AWS. | None — don't chase it |

---

## 3. Requirement → status → destination

| PDF requirement | Status | Destination | Source material |
|---|---|---|---|
| Abstract (200–300 words) | **Derivable tonight** | `docs/Project_Report.docx` | README §1 + "The gap this fills" |
| 15 papers, 2023–2026, indexed venues | **Missing — all 15** | `docs/Literature_Survey.docx` | PMD §15 has 33 refs, **0 pass both filters**; needs real search |
| Research gap, papers 1–5 (lead) | **Missing** | `docs/Research_Gap_Student1.docx` | Lead's own analysis; students 2–3 write their own |
| 4–6 objectives | **Derivable tonight** | `docs/Objectives.docx` | README "Core claims" C1–C5 |
| Novelty summary (≤1 page) | **Derivable tonight** | `docs/Novelty.docx` | README "The gap this fills" (CSPM / policy-as-code / FinOps triangle) |
| Diagram 1 — AWS architecture | **Missing, mandatory** | `architecture/AWS_Architecture.png` | PMD §6 three-account topology + stack |
| Diagram 2 — system architecture | **Missing, mandatory** | `architecture/System_Architecture.png` | FD-01 stage flow S1→S10 |
| Dataset details block | **Missing** | `dataset/dataset_description.pdf` | Synthetic corpus — answer honestly (see §6) |
| AWS services planning table | **Missing** | `docs/Project_Report.docx` | PMD §6 stack |
| `src/backend/` | Exists | `git mv kgcr/` | — |
| `src/ml_model/` | Exists as library | wrapper scripts | `kgcr/reconstruction/` |
| `src/aws/` | Exists | `git mv environment/` | Terraform budgets + cross-account IAM |
| `src/frontend/` | **Missing** | stub + Phase-II note | See §7 optional |
| `results/` | **Exists — your strongest material** | `git mv artifacts/` + numbers | DF-7 12/12, ECE ≤0.05 vs 0.28 |
| `presentation/` | **Missing** | deck | — |
| `LICENSE` | **Missing** | root | `pyproject.toml:11` says UNLICENSED |
| main / develop / feature branches | **Missing** | — | §4 step 4 |
| 20–30 commits + ≥2 PRs (lead) | **Achievable from here** | `feature/student1` | See §8 |

---

## 4. Migration (do this first, ~1 hour)

**Step 1 — create the repo, seed it with history.** Order matters: push before archiving.

Visibility is your call — `--public` if the reviewer needs to browse it without being added, `--private`
plus instructor access otherwise.

```bash
gh repo create KGCR_Cloud_Project_2026 --public --description "BCSE355L Cloud Architecture Design Project — Phase I"
```

Commit this plan first, or it stays stranded in the archived repo:

```bash
git -C /c/Projects/CCR add MIGRATION_PLAN.md && git -C /c/Projects/CCR commit -m "docs: Phase-I realignment plan"
```

```bash
git -C /c/Projects/CCR push https://github.com/uditdaftary/KGCR_Cloud_Project_2026.git master:main
```

**Step 2 — clone the new repo and work there.** `C:\Projects\CCR` becomes read-only reference.

```bash
git clone https://github.com/uditdaftary/KGCR_Cloud_Project_2026.git /c/Projects/KGCR_Cloud_Project_2026
```

**Step 3 — restructure on a branch.** One commit, `refactor: align tree with Phase-I guidelines`.

```
git mv kgcr            src/backend/kgcr
git mv environment     src/aws
git mv artifacts       results
mkdir  src/frontend src/ml_model dataset/raw dataset/processed presentation architecture
git mv roadmap.html roadmap.txt docs/     # not mandated; parked, don't let them shape the tree
```

Then the four config edits the move breaks — **all four, or the gates fail**:

| File | Line | Change |
|---|---|---|
| `pyproject.toml` | 46–47 | `[tool.setuptools.packages.find]` → add `where = ["src/backend"]` |
| `pyproject.toml` | 62–65 | `[tool.mypy]` → add `mypy_path = "src/backend"` |
| `pyproject.toml` | 11 | `license = { text = "UNLICENSED" }` → real licence once `LICENSE` lands |
| `.github/workflows/ci.yml` | — | check for hard-coded `kgcr/` paths |

Then fix stale path references in the **same commit** — every moved directory is named in prose a
reviewer will open (`logs.md:63` cites `artifacts/…`, `logs.md:6` links root `roadmap.html`, README
§Development documents `kgcr/` and `environment/` by path):

```bash
grep -rn --exclude-dir=.git -e 'artifacts/' -e 'environment/' -e 'roadmap.html' -e 'kgcr/' .
```

Re-run the gates exactly as `logs.md` §4 requires. **Nothing is "done" until these four pass:**

```bash
cd /c/Projects/KGCR_Cloud_Project_2026 && pip install -e ".[dev]" && ruff check . && ruff format --check . && mypy && PYTHONHASHSEED=0 pytest
```

Predicted (not yet run — nothing in this plan has been executed): 130 tests pass, as recorded in
`logs.md` §1. If the package move fights back, the fallback is §7 option B.

**Step 4 — branch topology** (PDF p.5–7):

```bash
git checkout -b develop main && git push -u origin develop
git checkout -b feature/student1 develop && git push -u origin feature/student1
```

Repeat for `student2`, `student3` — created as scaffolding so they have somewhere to work; the lead
does not commit to them. Set `develop` as the GitHub default working branch; protect `main`.

**Step 5 — `CLAUDE.md` + `CHANGELOG.md`** on `feature/student1`, landed into `develop` by PR (see §5).
That is PR #1 of the lead's required two, and it establishes the mandated workflow from the first change.

**Step 6 — archive `uditdaftary/KGCR`.** GitHub → Settings → Archive this repository. Add one line to
its README pointing at the new repo. **Do this last, and do it yourself** — I won't archive a repo
without you clicking it.

---

## 5. The two files

### `CLAUDE.md` (new repo) — distilled from the PDF

Contents, in this order:

1. **Submission facts** — BCSE355L, Dr. Priya V, Phase-I, deadline 30 July 2026, soft copy only
   (PDF/DOCX), presented at review alongside diagrams, survey, gaps, dataset, repo, progress.
2. **Mandated tree** — the exact structure from PDF p.5, marked as non-negotiable. Any new file
   goes into one of those directories.
3. **Branch workflow** — `feature/studentN` → PR → review → `develop` → `main` → tag `v1.0-Phase1`.
   Each student commits **only** to their own feature branch.
4. **Allocation** — papers 1–5 / 6–10 / 11–15, research gap docs, contribution matrix rows, with the
   lead's scope (papers 1–5, `feature/student1`) marked as the only one being authored here.
5. **Deliverable checklist** — the §3 table above, as checkboxes.
6. **Citation rules** — 2023–2026 preferred; IEEE / Springer / Elsevier / ACM / Wiley / MDPI /
   Nature / Scopus only; research gaps written from own understanding, never copied from the paper.
7. **Hard rules** — never fabricate a citation, a dataset URL, or a commit under another student's
   name. Quality gates (`ruff` / `mypy` / `pytest`) still gate every "done" claim.

### `CHANGELOG.md` (new repo) — the current `logs.md` verbatim

`logs.md` moves to `CHANGELOG.md` unchanged (phase table, implemented components, empirical results,
processes, decisions, gotchas, commit record), plus one new entry at the top:

```
## 2026-07-29 — Phase-I realignment
Repository re-created as KGCR_Cloud_Project_2026 with history preserved. Tree aligned to the
BCSE355L Phase-I guidelines. KGCR archived as reference-only.
```

---

## 6. Authoring order (the real work — tonight)

Ranked by "cannot be derived from anything in the repo":

1. **Literature survey — all 15 papers need fresh sourcing.** The single biggest item, and larger
   than it looks. PMD §15 has 33 references; **none satisfies both the venue and the date filter**.
   The four 2023–2026 entries (Self-Refine, Reflexion, Huang 2024, Sharma 2023) are NeurIPS / ICLR /
   arXiv — not on the IEEE / Springer / Elsevier / ACM / Wiley / MDPI / Nature / Scopus list. The
   ~6 that are venue-eligible (TPAMI, the ACM ones — Ratner VLDB, Joachims WSDM, Chaney RecSys,
   Bansal CHI, Buçinca CSCW) are all 2022 or earlier, so they only survive on the "prefer" reading
   of the date rule. Plan for 15 new searches on: cloud misconfiguration detection, IaC security
   analysis, knowledge graphs for cloud security, GNNs for configuration, compliance automation.
   **These must be searched and verified, not generated.** I will not invent citations. Table
   columns per PDF p.2: Paper / Method / Dataset / Advantages / Limitations / Research Gap.
2. **Two architecture diagrams** (mandatory). Diagram 1 from PMD §6 — three-account topology, Config
   + CloudTrail + CUR → S3 → Lambda/Glue → Neo4j, showing data flow, storage, processing, auth,
   notifications, monitoring. Diagram 2 from FD-01 stages S1→S10. Fastest honest route: author as
   Mermaid/SVG, export PNG.
3. **Research gap — `Research_Gap_Student1.docx` only**, own words, papers 1–5. Students 2 and 3
   write theirs; the survey table above still covers all 15 so the team document is complete.
4. **Abstract / objectives / novelty** — derivable from README + PMD in one pass.
5. **Dataset details** — see below.
6. **Report assembly → DOCX/PDF**, plus deck.

**Dataset honesty note.** The corpus is *synthetic and generated*, not downloaded. Fill the mandated
fields truthfully: Name = KGCR Corpus A (intent-first synthetic estates); Source = generated by
`src/backend/kgcr/corpus/`, seed-deterministic; URL = the repo, not a Kaggle link; Size / Records =
the actual 180-estate reconstruction corpus and the 12 DF-7 estates; Features = the intent axes
(archetype, AZ spread, network layout, logging posture, IAM shape, tagging, scale); License = none
(self-generated); Preprocessing = structural feature extraction. Corpus D (adversarial, licence-
enforcing registry) is schema-only and should be listed as planned, not present.

---

## 7. Lazy vs full, where it matters

**`src/ml_model/`** — full: split `kgcr.reconstruction` out into a standalone package (breaks
imports across 13 tests, not worth it tonight). **Lazy, recommended:** three thin entry-point scripts
`preprocessing.py` / `train.py` / `predict.py` wrapping `kgcr.reconstruction.pipeline`, writing
`model.pkl`. Matches the PDF's named files exactly and they actually run.

**`src/frontend/`** — nothing exists, and Phase-I doesn't require a working UI. **Lazy, recommended:**
a stub with a one-paragraph Phase-II scope note. Optional 30-minute upside: one static HTML page
rendering `results/p4_df7_checkov_evidence.json` and the reliability diagram — gives Student 1 a real
artifact for the "Frontend Development" row of the contribution matrix.

**Migration fallback (option B)** — if the package move breaks the gates and time runs out: leave
`kgcr/` at root and put pointer READMEs in `src/backend|ml_model|aws`. Structurally weaker and I'd
only take it under deadline pressure.

---

## 8. Things I will not paper over

- **Commit/PR attribution.** Scoped to the lead, the PDF's 20–30 commits and ≥2 PRs is reachable:
  the migration, the two governance files, each document, and each diagram are separate logical
  commits on `feature/student1`, landing through real PRs into `develop`. What stays off the table
  is backdating or authoring commits under students 2 and 3 — their branches exist, their sections
  are theirs.
- **Planned vs built.** The AWS services table is a *planning* table, which is correct for Phase-I.
  But the gap between the planned stack (SageMaker, Neo4j, Lambda, Cognito, QuickSight) and what runs
  today (local Python + a Terraform budget/IAM skeleton, never applied) is the most likely question
  at review. The report should state it plainly — the DF-7 12/12 result and the P8 calibration
  finding are strong enough to carry an honest scope statement.
- **Citations.** Searched and verified, or not included.

---

## 9. Tonight vs before review

**Tonight (submission-critical):** §4 migration → `CLAUDE.md` + `CHANGELOG.md` → 15 papers + survey
table → 2 diagrams → abstract / objectives / novelty / dataset / AWS table → assemble report to PDF.

**Before the review:** `Research_Gap_Student1.docx` finalised, presentation deck, `LICENSE`, optional
frontend page, tag `v1.0-Phase1`. Students 2 and 3 land their own gap docs on their own branches.

---

## 10. What breaks first

The 15-paper survey. Everything else is either a file move or a rewrite of text that already exists
in `docs/`; the survey is the only item requiring external sources that must be found and verified,
and it is also the item with three per-student dependencies hanging off it. Start there.
