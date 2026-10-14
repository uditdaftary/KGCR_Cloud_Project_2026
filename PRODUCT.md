# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python stdlib only: a `kgcr dashboard` subcommand serves a vanilla HTML/CSS/JS single-page app from
`src/frontend/` over `http.server`, with sessions and run history in a local `sqlite3` file. No new
dependencies (pyproject pins everything exactly). Bound to 127.0.0.1; no authentication by decision.

## Users

- **Operator (Udit, team lead)** drives the dashboard live at the BCSE355L Phase-I review, on his
  own laptop with a few people (the instructor, Dr. Priya V, and panel) around one screen.
- On the cover page the operator picks a role: **user** (a cloud architect or auditor reviewing an
  estate) or **admin** (the person who runs, evaluates and governs the system). No login.

## Product Purpose

KGCR recommends and reviews AWS configurations over a knowledge graph, and justifies every finding
as a traceable path from resource to regulatory control (PCI-DSS v4.0, CIS AWS Foundations) to a
consequence. The dashboard makes the whole project drivable without a terminal: every working
command, report and stored artifact is reachable from it. Success at the review: the operator can
run a review, show its reasoning in three audience renderings, and show the evaluation evidence and
governance state, without leaving the page.

## Positioning

Graph reasoning finds multi-hop violations (DF-5 to DF-7) that single-resource policy engines
cannot reach by construction; explanation is the evidence path itself, invariant in content across
audiences; the advisor reports irresolvable disagreement (CONTESTED) rather than manufacturing
agreement.

## Operating Context

- User side: pick a defect variant (9) and audience (architect, auditor, learner), run `kgcr
  review`, read findings, severity, control, evidence path, counterfactual, the three explanations;
  revisit session history; `explain` a stored run.
- Admin side: evaluation gates and reports (`results/*.json`), corpus generation, retrain/eval jobs
  (`src/ml_model/*.py`), job queue and all sessions, LLM fixture browser
  (`results/llm_fixtures/`), the six draft L1 controls, repro/environment info, AWS/Terraform status.
- Runs take seconds to minutes, so they execute as background jobs with visible progress.

## Capabilities and Constraints

- Working: `kgcr review`, `design`, `plan`, `apply`, `corpus`, `repro-info`, `history`, `explain`;
  evaluation scripts for advisor, recommender, reconstruction; intent prediction. The authoring
  tools (controls review, gold register) are human-only: the model may read, never write.
- Not built, listed on the Commands page with what would unblock each: live harvest, apply to a
  real account, recorded model reviews for four variants, instructor sign-off, the human study.
- Spend gate: every dashboard run replays recorded LLM fixtures by default. Live Gemini calls and
  real S3/SNS targets unlock only from the admin side behind a confirmation.
- Terminology: estate, variant, finding, control, evidence path, counterfactual, loop status
  (CONVERGED / CONTESTED), sycophancy gate, rule floor, intent axis, escalation.

## Brand Commitments

- Name: KGCR (Knowledge Graph-Based Cloud Configuration Recommendation). No logo exists.
- Global design rules (user CLAUDE.md): no rounded-full pill chips, no ALL-CAPS tracked fine print,
  no em or en dashes in rendered copy, no hype adjectives, sentence case, Linear-grade restraint.

## Evidence on Hand

- `results/advisor_report.json`, `recommender_report.json`, `reconstruction_report.json`;
  `runs-local/runs/*/` bundles and explanations; `results/llm_fixtures/`; the draft controls JSON;
  `architecture/*.png` diagrams; `docs/*.md`.
- The corpus is synthetic and self-generated; it must be labelled so. Control texts are drafts
  pending review. Nothing is deployed to AWS. No customers, users or benchmarks beyond the reports.

## Product Principles

1. Every number on screen is read from a report or run, never typed in.
2. Planned versus running is always visible.
3. The reasoning path is the explanation; show it, do not narrate around it.
4. Nothing spends money or touches real cloud without an explicit admin action.

## Accessibility & Inclusion

WCAG AA contrast, visible focus, full keyboard path, labels on every input, reduced-motion respected.
