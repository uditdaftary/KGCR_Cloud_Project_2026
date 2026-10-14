# KGCR — Knowledge Graph-Based Cloud Configuration Recommendation

Recommend a concrete AWS configuration from a workload stated in business terms, and justify every choice as a traceable subgraph linking it to a regulatory clause and a cost or risk consequence. Then run the same machinery in reverse on an existing estate, by first reconstructing the intent it was built to serve.

One-line framing: an experienced cloud architect who has read every compliance standard, never forgets one, and writes down their reasoning every single time.

> **BCSE355L Cloud Architecture Design Project — Phase-I submission.**
> Course instructor: Dr. Priya V. Team: Udit (lead), Manya, Tanmoy.
> Start with the [Project Report](docs/Project_Report.md); [CLAUDE.md](CLAUDE.md) is the governing
> document for how this repository is worked in.

## Phase-I deliverables

| Deliverable | File |
|---|---|
| Project report — abstract, AWS services plan, progress, contribution matrix | [docs/Project_Report.md](docs/Project_Report.md) |
| Literature survey — 15 papers, 2023–2026, DOI-verified | [docs/Literature_Survey.md](docs/Literature_Survey.md) |
| Research gap analysis — Udit, papers 1–5 | [docs/Research_Gap_Udit.md](docs/Research_Gap_Udit.md) |
| Objectives — six, each with a measure | [docs/Objectives.md](docs/Objectives.md) |
| Novelty summary | [docs/Novelty.md](docs/Novelty.md) |
| Diagram 1 — AWS Cloud Architecture | [architecture/AWS_Architecture.png](architecture/AWS_Architecture.png) |
| Diagram 2 — Complete System Architecture | [architecture/System_Architecture.png](architecture/System_Architecture.png) |
| Dataset details | [dataset/dataset_description.md](dataset/dataset_description.md) |

Each is also generated as `.docx` for submission (`python docs/make_docx.py`); the Markdown is the
source of truth.

**Implementation status.** Review mode runs end to end locally as one command,
`kgcr review`: estate, dependency graph, intent reconstruction (P8), recommendation with a hard
CRITICAL mask (P7), the bounded advisor loop (P6), and the explainer (P9). Design mode now runs
the same machinery forward: `kgcr design` builds a spec from an intent, `kgcr plan` turns a
reviewed spec into an immutable plan with a cost delta, and `kgcr apply` applies it to a local
simulation. `kgcr dashboard` drives all of it from a local browser page.

Verification: 474 tests pass on the build machine (Python 3.14, with Checkov, Trivy and Terraform
installed). In a clean Python 3.12 venv with only the dev extra the same gates are clean and 457
pass, 4 skip. CI runs the gates on Python 3.11 and 3.12 for every push. What is not done:

- Nothing has touched a real AWS account. The Terraform-backed apply and the AWS Config harvest
  adapter are built and tested against fakes only (no credentials here). `src/aws/` validates
  under Terraform v1.16.5 and is not applied.
- The advisor's live run happened once: sycophancy gate PASS on 3 valid trials (1 invalid), 2 of 4
  relational or resilience variants found, 1 false CRITICAL on 4 clean estates. Recorded responses
  replay offline from `results/llm_fixtures/`; the other four variants have no recording because
  the free-tier quota was spent (`src/ml_model/record_variants.py` is ready).
- The L1 control slice is a draft awaiting Udit's review; the dashboard has the review tools, and
  no control has been signed off.
- The human study (P11) needs ethics approval and participants.
- The corpus is synthetic. Corpus D (TerraGoat and CloudGoat) checks the rule floor against
  independently written configurations: it covers 2 to 4% of what Checkov fails there.

The `docs/` FD set remains the controlling specification.

## The gap this fills

Existing tools each cover one edge of the problem and none cover the middle:

- **CSPM** (Wiz, Prisma Cloud, Orca) detects violations in what already exists. No design-time recommendation.
- **Policy-as-code** (Checkov, tfsec, Prowler, OPA) checks one resource at a time. No recommendation, no justification beyond rule text, and by construction it cannot see multi-hop defects.
- **FinOps** (CloudHealth, Cloudability) finds waste but is compliance-blind.

The unoccupied intersection is design-time recommendation, compliance grounding, cost joint-optimisation, and audit-grade explanation, over a single graph representation. That intersection is this project.

## Core claims

| | Claim |
|---|---|
| **C1** | A graph representation detects multi-hop compliance violations that single-resource policy engines cannot reach by construction. |
| **C2** | Configuration review reframed as design with reconstructed intent: a review is a design whose intent was recovered rather than supplied. |
| **C3** | Explanation is the reasoning path itself, extracted from the graph, not prose narrated after the fact. Because the compliance logic is curated, most explanations are exact rather than approximate. |
| **C4** | Explanation is audience-relative in form but invariant in content. What the system concludes never changes with who is reading. |
| **C5** | Bounded adversarial review that reports irresolvable disagreement rather than manufacturing agreement. |

## Documents

Start with the [PMD](docs/PMD.md); it binds the rest. The FD documents specify individual subsystems.

| ID | Document | Covers |
|---|---|---|
| PMD | [Project Master Document](docs/PMD.md) | Thesis, scope, decision register, milestones, risk, commercial analysis |
| FD-01 | [Unified Flow Specification](docs/FD-01_Unified_Flow_Specification.md) | The single pipeline, its stages, terminal states, invariants, CLI |
| FD-02 | [Advisor Iteration Policy](docs/FD-02_Advisor_Iteration_Policy.md) | Bounded review loop, severity taxonomy, contested findings |
| FD-03 | [Feedback Loop Specification](docs/FD-03_Feedback_Loop_Specification.md) | Run records, L1/L2/L3 layering, learning uses, feedback pathologies |
| FD-04 | [Advisor Persona Specification](docs/FD-04_Advisor_Persona_Specification.md) | Reviewer role, the grounding rule, calibration, independent evaluation |
| FD-05 | [Data Strategy and Corpus Construction](docs/FD-05_Data_Strategy_and_Corpus_Construction.md) | Corpus sources, defect taxonomy, weak supervision, circularity defences |
| FD-06 | [Explainer Specification](docs/FD-06_Explainer_Specification.md) | Subgraph extraction, counterfactuals, audience modes, XAI evaluation |
| FD-07 | [Ontology Specification](docs/FD-07_Ontology_Specification.md) | L1 node/edge schema, control-to-config crosswalk, severity derivation, FIBO/OSCAL |
| FD-08 | [Environment Build](docs/FD-08_Environment_Build.md) | Three-account topology, cross-account IAM, cost controls, Phase 0 exit |

## Scope

Deliberately narrow, to demonstrate depth rather than breadth:

- **Three workload archetypes:** payments API (cardholder data), customer data platform (PII), internal reporting service (cost-dominant contrast case).
- **Two enforced frameworks:** PCI-DSS v4.0 and CIS AWS Foundations Benchmark. NIST 800-53 / OSCAL is a cross-reference and export layer; FIBO anchors the financial domain.

## Interface

Working today (local, synthetic corpus):

```
kgcr dashboard [--port 8765] [--open]                     # the local dashboard, below
kgcr review [--variant <defect>] [--audience architect|auditor|learner] [--out <dir>]
            [--s3-bucket <name>] [--sns-topic-arn <arn>]    # AWS targets, opt-in
kgcr design  --archetype <a> --region <r> --az-spread <s> --network-layout <n> --logging <l>
             --iam-shape <i> --tagging <t> --scale <c> [--audience <a>] [--out <dir>]
kgcr design  --statement "<free text>" [--extract-only]    # Gemini extracts; unresolved fields stay empty
kgcr plan    --spec <run-id prefix> [--backend local|terraform] [--json] [--out <dir>]
kgcr apply   --plan <plan-id> [--backend local|terraform] [--confirm <plan-id>] [--budgets-applied]
                                                          # terraform: gated, never run
kgcr history [--out <dir>] [--json]                       # stored runs
kgcr explain --run <run-id prefix> [--audience <a>]       # re-render a stored run
```

Not built: `kgcr review --account <id>`. The AWS Config adapter behind it exists
(`kgcr.harvest.config`) and is not wired into review or run against an account.

### Dashboard

`kgcr dashboard` serves a local single-page dashboard on `127.0.0.1:8765` that drives every
working command without a terminal. The cover offers two roles, user and admin; there is no
login by design. Sessions, jobs and run history live in `runs-local/dashboard.sqlite3`.

- **User side:** pick one of the nine seeded defect variants and an audience, run a review, then
  read the estate graph, each finding's evidence path and counterfactual, the measured pipeline
  timings, and the three audience renderings with their shared claims pinned. History lists every
  stored run. A design page builds a spec from the eight intent axes or from a sentence (the model
  extracts, the operator confirms the form); a plan page shows a run's lifecycle, makes a plan with
  a cost delta, and applies it to the local simulation.
- **Admin side:** gates and reports, a job launcher and queue (corpus, advisor evaluation,
  reconstructor training, recommender evaluation, intent prediction, the CI gates, the static
  results page), sessions, recorded model fixtures, the controls review and gold set pages
  (append-only; the reviewer is never the author; the model may read the controls but never
  writes them), the environment fingerprint, cloud and spend, the command surface (including what
  is not built), and the project files.
- **Spend gate:** every dashboard job replays recorded model responses (`KGCR_LLM_LIVE=0` is forced
  in the child process). Live Gemini calls and real S3/SNS targets need an admin to enable live
  mode, which resets on every server restart.
- Jobs write into `runs-local/jobs/KG<no>/`; nothing the dashboard runs overwrites `results/` or
  `dataset/processed/`.

`--audience` (`architect` / `auditor` / `learner`) changes only how a result is rendered. The underlying reasoning and conclusions are identical across renderings; this invariant is tested, not asserted.

## Roadmap

The milestone plan (PMD §10) is dependency-ordered and phase-based. The generator, labelling
pipeline, Advisor, Recommender, intent reconstructor, Explainer, and design, plan and apply are
built locally (see the status above). What is left is what needs a person or an account:

1. **Phase 0 — environment** (FD-08): three accounts wired, budget alarms live, cross-account read working. The Terraform validates and is not applied; the harvest and the real apply wait on this.
2. **Phase 1 — ontology** (FD-07): the six draft L1 controls need Udit's review. The dashboard has the review tools; no control has been signed off. This is the foundation every compliance claim rests on, and the phase most likely to be underestimated.
3. **Phase 2 — gold set** (FD-05 §4C): 50 to 100 hand-verified reference configurations that validate the L1 encoding. The register exists and freezes on instructor sign-off; it holds none yet.
4. **Evaluation and human study** (P11): the automated half is in `results/explainer_report.json`; the human study needs ethics approval and participants.

## Development

Requires Python 3.11+. [docs/Runbook.md](docs/Runbook.md) is the step-by-step version of this
section: setup, gates, every demo with its expected output, the optional tools, and
troubleshooting.

```bash
pip install -e ".[dev]"     # install with dev tooling (pinned versions)
ruff check . && ruff format --check . && mypy && PYTHONHASHSEED=0 pytest   # the CI gates
kgcr repro-info             # print the seed + version fingerprint for this env
kgcr corpus --count 500     # [dev] generate Corpus A and parse it into the graph
kgcr dashboard --open       # drive everything from the browser
```

Run the demo and regenerate the results:

```bash
kgcr review --variant unencrypted_database --audience auditor   # end-to-end review, ~15 s
kgcr review --variant transitive_trust_chain   # DF-7: found only with recorded LLM fixtures
kgcr design --archetype payments_api --region eu-west-1 --az-spread two_az \
    --network-layout public_private --logging full --iam-shape least_privilege \
    --tagging strict --scale small                # a designed spec, audited by the recommender
kgcr plan --spec <run-id prefix>               # diff, coverage, blast radius, monthly cost delta
kgcr apply --plan <plan-id>                    # local simulation; one apply per plan
python src/ml_model/train_recommender.py       # results/recommender_report.json
python src/ml_model/run_advisor.py             # results/advisor_report.json
python src/ml_model/run_explainer_eval.py      # results/explainer_report.json
```

Needing more than the dev extra, none of it in CI: `run_corpus_d.py` (`.[adversarial]` and
`acquire_corpus_d.py`), `run_labeller_agreement.py` (Checkov, Trivy and Terraform),
`gnn_ablation.py` (`.[gnn]`), and `kgcr plan --backend terraform` (Terraform). Terraform is
found even when PATH predates its install.

Live Gemini calls (`gemini-3.7-flash`) need `pip install -e ".[advisor]"`, `GEMINI_API_KEY`, and
`KGCR_LLM_LIVE=1`. They are capped at 24 per run and recorded under `results/llm_fixtures/`, so
tests and later runs replay them offline. The free tier allows about 20 requests a day;
`python src/ml_model/record_variants.py` records the four variants that have no recording yet and
stops at the first quota refusal. Put both in a git-ignored `.env` (copy `.env.example`) or export them; the key is never written.

The tree follows the BCSE355L Phase-I guidelines (`docs/`, `architecture/`,
`dataset/`, `src/{frontend,backend,ml_model,aws}`, `results/`, `presentation/`);
[CLAUDE.md](CLAUDE.md) is the governing document.

- `src/backend/kgcr/` — the package. It provides the reproducibility spine
  (`repro`, `hashing`, `runrecord`, `versions`) that keys every result to
  `(spec_hash, graph_version, model_version)`, plus the `kgcr` CLI described under
  [Interface](#interface).
- `src/ml_model/` — entry points for the P8 intent reconstructor:
  `preprocessing.py` (generate the corpus into `dataset/processed/`), `train.py`
  (fit, write `model.pkl` and the evaluation report), `predict.py` (reconstruct
  one estate's intent with per-field confidence). Thin wrappers over
  `kgcr.reconstruction`; the library is where the logic and its tests live.
- `src/frontend/` — the dashboard page (`index.html`, `app.js`, `plot.js`, `app.css`, self-hosted
  OFL fonts) served by `src/backend/kgcr/dashboard/`, plus `build_dashboard.py`, which writes the
  static offline results page `results/dashboard.html` for the submission.
- `src/backend/kgcr/corpus/` — Phase 3 (FD-05 §4A): the **intent-first** synthetic estate
  generator. An intent is sampled first (`intent`, `sampler`), an estate is
  rendered from it (`generator`, `estate`) carrying that intent as ground truth,
  and it is parsed into a dependency graph either directly (`graph`) or from a
  real `terraform show -json` plan (`plan_parser`). `splits` enforces
  estate-level, seed-family train/test separation (FD-05 §9); `pipeline` runs
  the whole thing. The corpus is clean at this phase — defect injection is
  Phase 5. No `terraform`/AWS is required to generate it.
- `src/backend/kgcr/recommender/` — P7: options retrieved from the clean and
  defect corpora, ranked from intent, then filtered by a hard CRITICAL mask.
- `src/backend/kgcr/advisor/` — P6: rule floor, Gemini proposals behind an
  admission filter, the FD-02 bounded loop, and the sycophancy protocol. The L1
  slice it grounds in is `controls_DRAFT-FOR-UDIT-REVIEW.json`.
- `src/backend/kgcr/explainer/` — P9: exact justifications, counterfactuals by
  re-evaluation, three audience renderings, and the INV-2 claim-extraction test.
- `src/backend/kgcr/orchestration/` — P10: the `kgcr review` pipeline and the
  local stand-ins for the S3 run bucket and the SNS topic.
- `src/backend/kgcr/design/`, `plan/`, `apply/` — design mode, plans with a cost delta
  (`plan/aws_prices.json` holds verified AWS list prices), and the local and Terraform-backed apply.
  `harvest/` is the AWS Config adapter (never run against an account). `gold/` and
  `dashboard/authoring.py` are the human-only authoring tools. `adversarial/` reads Corpus D.
- `src/ml_model/` also holds `run_corpus_d.py`, `run_labeller_agreement.py`,
  `run_explainer_eval.py`, `gnn_ablation.py` (optional `gnn` extra) and `record_variants.py`.
- `src/aws/` — the FD-08 §8 bootstrap Terraform: day-one budget alarms and
  the cross-account read/write role split. Validated with Terraform v1.16.5, not applied.
- `.github/workflows/ci.yml` — ruff, mypy, and pytest on every push.

## Context

This is an academic project spanning cloud architecture and applied AI. It is trained and evaluated on a synthetic, mined, and adversarial corpus; no real financial-sector data is used, and that limitation is stated openly in FD-05. The commercial analysis in PMD §12 is candid about what a student build can and cannot substantiate.
