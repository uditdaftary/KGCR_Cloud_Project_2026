# KGCR_Cloud_Project_2026 — working rules

Governing document for this repository. Derived from **BCSE355L Cloud Architecture Design Project,
Phase-I Guidelines** (Course instructor: Dr. Priya V). Where this file and the guidelines disagree,
the guidelines win.

Project narrative, phase status, and build history live in [CHANGELOG.md](CHANGELOG.md).
The migration that produced this repo is [MIGRATION_PLAN.md](MIGRATION_PLAN.md).

---

## 1. Submission facts

| | |
|---|---|
| Course | BCSE355L — Cloud Architecture Design Project, Phase-I |
| Instructor | Dr. Priya V |
| Deadline | **30 July 2026** |
| Format | Soft copy only (PDF or Microsoft Word). No hard copy. |
| Cloud | AWS |
| At review | Present the report with architecture diagrams, literature survey, research gap analysis, dataset details, the GitHub repository, and implementation progress. Each student explains their own contributions, commit history, and AWS service integration. |

## 2. Scope of work in this repository

Team of three. **Everything authored here is Udit's (as team lead) contribution.** Manya and Tanmoy
have branches and own their sections; nothing is written or committed on their behalf.

| | Udit (lead) | Manya | Tanmoy |
|---|---|---|---|
| Literature survey | Papers 1–5 | Papers 6–10 | Papers 11–15 |
| Research gap doc | `docs/Research_Gap_Udit.docx` | theirs | theirs |
| Branch | `feature/udit` | `feature/manya` | `feature/tanmoy` |

## 3. Mandated repository structure

Non-negotiable — from the guidelines, p.5. **Every deliverable file goes into one of these
directories.** Repository governance, build configuration, and the test suite (`CLAUDE.md`,
`CHANGELOG.md`, `MIGRATION_PLAN.md`, `pyproject.toml`, `tests/`) stay at the root.

```
KGCR_Cloud_Project_2026/
├── README.md
├── LICENSE
├── .gitignore
├── docs/            Project_Report, Literature_Survey, Research_Gap, Objectives, Novelty
├── architecture/    AWS_Architecture.png, System_Architecture.png, Workflow.png
├── dataset/         raw/, processed/, dataset_description.pdf
├── src/             frontend/, backend/, ml_model/, aws/
├── results/
└── presentation/
```

## 4. Branch workflow

```
main ← develop ← feature/udit | feature/manya | feature/tanmoy
```

- Each student commits **only** to their own feature branch. Never commit feature work to `develop`
  or `main` directly.
- Feature branch → Pull Request → team review → resolve conflicts → merge into `develop`.
- When the project is stable, merge `develop` into `main` and tag `v1.0-Phase1`.

Expected GitHub activity per student: 20–30 meaningful commits, at least 2 Pull Requests, code-review
participation, regular weekly commits, continuous documentation updates. Conventional commits, one
logical change each; no AI co-author or "Generated with" trailers.

## 5. Required report sections

- [ ] **Abstract** — 200–300 words: problem statement, existing challenges, proposed solution, AWS services used
- [ ] **Literature survey** — 15 papers, table columns: Paper / Method / Dataset / Advantages / Limitations / Research Gap
- [ ] **Research gap analysis** — per student, for their five papers: existing methods, advantages, limitations, research gap, possible improvement
- [ ] **Objectives** — 4–6, measurable and achievable
- [ ] **Novelty summary** — max one page: what makes this different (feature, algorithm, architecture, AWS integration, security, automation, accuracy, scalability)
- [ ] **Proposed architecture** — two diagrams, both mandatory
      - Diagram 1, AWS Cloud Architecture: how AWS services interact — data flow, storage, processing, authentication, notifications, monitoring
      - Diagram 2, Complete System Architecture: the overall project workflow
- [ ] **Dataset details** — name, source, URL, size, number of records, number of features, data type, license, purpose, preprocessing required
- [ ] **AWS services planning** — every service planned for implementation, with its purpose

## 6. Citation rules

- Venues: **IEEE, Springer, Elsevier, ACM, Wiley, MDPI, Nature, Scopus-indexed journals** only.
- Prefer **2023–2026**.
- Research gaps are written from your own understanding. **Never copy a research gap out of the paper.**

## 7. Hard rules

- **Never fabricate** a citation, a venue, a dataset URL, or a result. Searched and verified, or not included.
- **Never commit under another student's name**, and never backdate history.
- The corpus is **synthetic and self-generated**. Say so in the dataset section; do not dress it up
  with an external source or a license it does not have.
- The AWS services table is a **planning** table (correct for Phase-I). State plainly what is planned
  versus what runs today — the review will ask.
- Quality gates still gate every "done" claim. Run exactly as CI does, with `PYTHONHASHSEED=0`:

```bash
ruff check . && ruff format --check . && mypy && PYTHONHASHSEED=0 pytest
```
