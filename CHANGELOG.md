# CHANGELOG — KGCR build log: processes and progress

Knowledge Graph-Based Cloud Configuration Recommendation framework. This file
records what has been built, how it was built (the processes and quality gates),
and what is deliberately deferred. It is maintained alongside the roadmap
([docs/roadmap.html](docs/roadmap.html)) and the FD specification set in [docs/](docs/).
Working rules for this repository live in [CLAUDE.md](CLAUDE.md).

Last updated: 2026-10-14.

---

## LOOP_STATE (updated in place, never stacked)

Updated 2026-10-14. Branch `feature/udit`, 24 local commits ahead of `origin/feature/udit`, **not
pushed, no pull request opened** for this pass (spec decision D4: one local commit per slice). PRs
#6, #8 and #9 are merged. The account for what ran and what did not is in section 0b below.

- **Built and run in this pass** (spec `docs/superpowers/specs/2026-10-13-design-plan-apply-authoring-design.md`,
  plan beside it):
  - **`kgcr design`:** a generator skeleton audited and patched by the option recommender, with a
    per-choice justification taken from the findings of the alternatives it rejected. Structured
    intake, and free-text intake through Gemini where a value is admitted only if its evidence is a
    quotation of the statement; anything unresolved stays empty and the operator confirms the form.
  - **`kgcr plan`:** immutable plans under `runs/<prefix>/plans/<plan_id>/` with a local diff,
    coverage, blast radius and a monthly cost delta from AWS list prices. A Terraform backend runs
    `init`, `validate` and an offline `plan` with mock credentials.
  - **`kgcr apply`:** a local simulated apply (partial state kept on failure), and a Terraform-backed
    path behind refusal gates. **That path was never run.**
  - **Dashboard:** design, plan and apply pages, and authoring pages for the L1 controls review and
    the gold register. Append-only, reviewer is never the author, a CRITICAL comment blocks
    sign-off, and an AST test keeps `kgcr.gold` out of everything but the dashboard.
  - **Corpus D:** TerraGoat and CloudGoat parsed (never executed), rule floor against Checkov.
  - **Second labeller:** Trivy, with Cohen's kappa against the rule floor and Checkov.
  - **FD-06 automated evaluation:** `results/explainer_report.json`.
  - **GNN ablation:** `results/gnn_ablation.json`.
  - **AWS Config harvest adapter:** `harvest/config.py`. **Never run against an account.**
  - **Variant recorder:** `src/ml_model/record_variants.py`, ready, **waiting on the Gemini quota.**
- **Verified by running:** Terraform v1.16.5 (installed with winget) validates `src/aws/`; nine
  generated estates (three archetypes, three zone and layout pairs) validate and plan offline after
  the overlay; free-text intake ran against live Gemini and three responses are recorded and replay
  (`results/llm_fixtures/intent-v1-*.json`); every list price in `aws_prices.json` was re-derived
  from freshly downloaded official files and matched.
- **Gates:** 474 tests pass; ruff check, ruff format --check and mypy (82 source files) are clean. The CI gates run on Python 3.11 and 3.12; this machine runs 3.14.3.
- **Not done, and why** (the dashboard's Commands page lists the same six):
  - **Live harvest, real-AWS apply:** no AWS credentials on this machine. Both are authored and
    tested against fakes (botocore stubs, moto for S3) and have never touched an account.
  - **Recorded Gemini reviews for seven variants:** the free tier allows 20 requests a day and the
    day's quota was used verifying free-text intake. A retry on 2026-10-14 got a 429 on the first
    call. Re-run `python src/ml_model/record_variants.py` after the quota resets.
  - **Human study (P11):** needs ethics approval and participants. Not simulated.
  - **Instructor sign-off of controls and gold set:** the tools exist; sign-off is a human act.
  - **Weak-supervision label model (P4):** not built.
- **Findings from this pass that change what the project can claim:**
  - Generated estates **failed `terraform validate`** as rendered (no load balancer subnets, an
    empty encryption rule, no database credentials). A render-time overlay now completes them and
    reports every addition. That makes a plan validate; it does not make an apply succeed.
  - The shipped write role (`ec2`, `s3`) blocks every generated estate at the permission preflight.
    `provision_services` widens it; the default is unchanged.
  - In independent repositories the rule floor's families cover 31 of the 787 checks Checkov fails
    in CloudGoat (4%) and 5 of 215 in TerraGoat (2%). Where it can read the values it agrees with
    Checkov (database and CloudTrail families); it misses where an argument is an unresolved
    expression (16 CloudGoat security groups, 2 IAM policies). See section 0b.
  - Checkov's `.tf.json` input recalled none of the 24 seeded defects; its plan-JSON input is the
    fair one. Trivy and Checkov do not treat a world-open port 443 as a defect.
  - The GNN expectation ("no gain") was only partly right. See section 0b.
- **Also open:**
  - Dashboard JavaScript has no lint or test gate; it is verified by driving it in a browser.
    The new pages were driven through the API and the DOM; screenshots were not captured because
    the browser pane was hidden, and the pages use components from the approved system rather than
    a new scheme.
  - Replay covers two variants at seed 1729, size 180 (DF-5 `no_database_backup`, DF-7
    `transitive_trust_chain`); the roster labels the other seven as rule floor only.
  - An offline planfile cannot be applied: the Terraform-backed apply re-plans against the live
    provider and refuses unless the creates equal the reviewed plan.
- **Awaiting Udit's review:**
  - The six draft L1 controls, all unverified.
  - `docs/*.docx` were deleted from git on 2026-07-31. They are regenerated locally, not
    re-committed.
  - `make_docx.py` rewrote `dataset/dataset_description.docx`. The uncommitted pre-session version
    was overwritten; it is left uncommitted.

---

## 0b. 2026-10-13 and 14 — design, plan, apply, authoring, and the blocked items

Asked for every unbuilt feature on the dashboard, in order, with a spec first; then to install
Terraform, finish the blocked items, let live Gemini verify free-text intake, and have a Haiku
subagent research the plan's cost data. The spec and plan are in `docs/superpowers/`. Scope
decisions taken with the user: design, plan and apply only (later widened to the blocked items);
apply also gets a Terraform-backed path; authoring tools for the controls and gold set live in the
dashboard. Spec decisions D1 to D4: each design choice is justified from its rejected
alternatives; the generator skeleton is audited by the recommender; exports are browser
downloads; one local commit per slice on `feature/udit`, no push, no pull request.

**What was built**

- **Design (`kgcr design`).** A generator skeleton, audited and patched by `OptionRecommender`. A
  masked option that reaches the skeleton raises `MaskViolation`. The explanation bundle gains a
  `design` key only when it has content, so stored bundles stay byte-identical. Free-text intake:
  Gemini extracts into the fixed eight-field schema, and a value is admitted only if it is in the
  schema and its evidence is a quotation of the statement; otherwise the field is null and the
  operator confirms the form.
- **Run lifecycle.** Runs record `mode` (review or design), the observed spec, and events
  (`planned`, `applied`, `apply_failed`). INV-1: no spec with an open CRITICAL reaches a plan.
- **Plan (`kgcr plan`).** Immutable `runs/<prefix>/plans/<plan_id>/plan.json`; the id is the first
  16 hex of the canonical hash of spec, baseline, backend and overlay. Local diff, coverage from
  `resource_findings`, blast radius, and a cost delta. The Terraform backend runs `init`,
  `validate` and an offline `plan` with mock credentials, for design runs only.
- **Deployable overlay (`plan/deployable.py`).** Completes the arguments the provider requires and
  reports every addition and every caveat (availability zones, the encryption rule, load balancer
  subnets, database credentials via `manage_master_user_password`, a placeholder image id, security
  group rule keys). It makes a plan validate. It does not make an apply succeed.
- **Cost data.** A Haiku subagent collected AWS list prices from the official files; the main thread
  then re-derived every EC2, RDS, load balancer, KMS and S3 value from freshly downloaded files and
  read CloudTrail and Glue by SKU. All matched (the checking script is not committed). 45 items,
  three regions, retrieved 2026-10-13, 730 hours a month (this tool's own convention, labelled).
  What cannot be priced is listed, never zeroed.
- **Apply (`kgcr apply`).** Local: a simulated deploy that keeps partial state on failure.
  Terraform-backed: refuses in order unless real applies are switched on, the plan and spec hash
  hold, the plan is a Terraform plan, the binary exists, the preflight passes against the write
  role's grant, the plan id is typed, the budget alarms are acknowledged, the image is real, the
  role, external id and account are set, the plan was not already applied, and the assumed account
  matches. It then re-plans against the live provider and refuses unless the creates equal the
  reviewed plan. **Authored and tested against fakes only. No apply was ever run and nothing
  assumed a role or called AWS.** The write role gains an opt-in `provision_services` variable
  (default unchanged); the preflight and the Terraform are kept equal by a drift test.
- **Dashboard.** Design, plan and apply pages; the run sleeve shows design runs. Authoring pages
  for the controls review and the gold register: append-only, reviewer is never the author, a
  CRITICAL comment blocks sign-off, the register freezes on instructor sign-off, exports are
  downloads. An AST test keeps `kgcr.gold` out of everything but the dashboard, so the advisor
  can never read the gold register.
- **Corpus D.** TerraGoat and CloudGoat cloned shallow into an untracked directory, licences read
  from their own LICENSE files, commits pinned, parsed with `bc-python-hcl2` and never executed.
- **Second labeller.** Trivy as a subprocess engine, with Cohen's kappa. The family mapping from
  check ids to defect families is this project's own.
- **FD-06 automated evaluation** (`explainer/evaluate.py`): invariance, counterfactual validity
  checked against the loop's observed outcome, sparsity, and relational Fidelity+ and Fidelity-.
- **AWS Config harvest adapter** (`harvest/config.py`): an injected client, `list_discovered_resources`
  and `batch_get_resource_config`, field names from the AWS Config resource schema, five types.
  Skipped and unprocessed resources are listed. It reads no tags (the batch API strips them) and
  no networks or IAM.
- **Variant recorder** (`record_variants.py`): idempotent, budgeted, stops at the first quota
  refusal.
- **GNN ablation** (`gnn_ablation.py`, optional `gnn` extra, outside CI).

**What was run, and what came out**

- **Terraform v1.16.5** installed with winget. `src/aws/` validates. Raw generated estates did
  **not** validate; with the overlay nine of them (three archetypes, three zone and layout pairs)
  validate and plan offline in 101 to 143 seconds each. A seeded open-security-group estate then
  failed validation because the provider requires every key on a rule; the overlay now completes
  them.
- **Live Gemini, free-text intake.** Three extractions ran and are recorded
  (`results/llm_fixtures/intent-v1-*.json`) and replay. The first attempts met 503 (transient), so
  `GeminiClient` now retries twice and extraction failures are reported as unavailable. Later
  attempts met 429, the free tier's 20 requests a day. A retry of the variant recorder on
  2026-10-14 got 429 on its first call.
- **Corpus D.** CloudGoat 740 AWS resources, TerraGoat 63. The rule floor's families cover 31 of
  787 Checkov failures in CloudGoat (4%) and 5 of 215 in TerraGoat (2%). Agreement where values are
  readable: database encryption and CloudTrail validation. It misses where an argument is an
  unresolved expression (16 security groups, 2 IAM policies). No per-resource labels exist, so
  this is agreement and coverage, not accuracy.
- **Three-engine agreement**, 6 seeded estates per family, 24 seeded and 24 clean units, Checkov
  3.3.8 on plan JSON and Trivy 0.75.0 on `.tf.json`. Seeded recall: rule floor 1.0 everywhere (by
  construction); Checkov 0 on DF-1 and 1.0 on DF-2, DF-3, DF-4; Trivy 1.0 on DF-2 and DF-4 and 0 on
  DF-1 and DF-3. No false positives on any clean parent. Kappa between Checkov and Trivy: 1.0 on
  DF-2 and DF-4, 0.0 on DF-3, undefined on DF-1. DF-1 is the injector's world-open port 443, which
  neither tool treats as a defect: a disagreement about the definition, not an engine error. Checkov
  reading `.tf.json` recalled 0 of 24 (`results/labeller_agreement_tfjson.json`), which is why plan
  JSON is the input. Small n: indications, not rates.
- **FD-06 evaluation**, 12 bundles (nine variants, three designs): invariance 12 of 12; counterfactual
  validity 4 of 4; sparsity mean 0.078, median 0.059, max 0.2 over 7 findings; Fidelity+ and
  Fidelity- 1 of 1 each. The samples are tiny because recorded model responses exist for only two
  variants, so most bundles are rule floor only. The human study (§9.3) is not run.
- **GNN ablation.** Expectation recorded before running: no gain. Over 99 test estates in four
  corpus seeds, exact-set recovery: forest 0.941, two-layer network over the resource-type graph
  0.991, the same network with edges removed 0.984. R-precision and NDCG are saturated for the
  forest. So the expectation was partly wrong: a neural ranker is a little better at exact-set
  recovery, and the edge-free control says the graph is not why. torch 2.14.1 has a cp314 wheel,
  so this was not blocked by the environment; it ran in a throwaway venv.

**Findings that change what the project can claim**

- Generated estates were never deployable as rendered; they needed the overlay to validate.
- The shipped write role (`ec2`, `s3`) blocks every generated estate at the preflight.
- The rule floor is a small slice of real-world failures (2 to 4% in independent repositories).
- Checkov's `.tf.json` input is not a usable recall baseline; its plan-JSON input is.
- An offline planfile cannot be applied, so the spec's wording ("apply the saved planfile") was
  corrected to what is built: re-plan live and compare.

**Not run, and why**

- Live harvest and any real apply: no AWS credentials on this machine.
- Recorded reviews for seven variants: the daily free-tier quota is spent. `record_variants.py` is
  ready; the first call on 2026-10-14 was refused.
- Human study (P11): needs ethics approval and participants. Not simulated.
- Controls and gold-set sign-off: the tools exist; sign-off is a human act.
- Browser screenshots of the new pages: the browser pane was hidden, so they were driven through
  the API and the DOM instead. The pages use components from the approved Catalog Sleeve system; no
  new scheme was introduced and no pre-code render was made.

**What would break first.** The overlay: it is the only thing between a generated estate and a
provider that rejects it, and every real apply will find the next missing argument.

---

## 0a. 2026-07-30 — Phase-I deliverables authored

- **Naming.** Team members are named throughout: Udit (lead), Manya, Tanmoy.
  Feature branches renamed `feature/udit`, `feature/manya`, `feature/tanmoy`.
  The GitHub branch rename **closed PR #1** rather than retargeting it; the work
  was reopened as a new pull request from `feature/udit`.
- **Literature survey** — 15 papers, 2023–2026, all in IEEE / Springer /
  Elsevier / ACM / MDPI venues, every record verified against Crossref. 13 of 15
  abstracts read; papers 10 and 15 are metadata-verified only and flagged for
  library access. None of the 33 references in PMD §15 satisfied both the venue
  and the date filter, so all 15 were sourced fresh.
- **Both mandatory architecture diagrams** generated by
  `architecture/make_diagrams.py` — a layout script emitting backend-neutral
  primitives that a Pillow renderer and an SVG renderer both walk, so the PNG and
  SVG cannot drift. Diagram 1 is the planned AWS service topology (PMD §6);
  Diagram 2 is the FD-01 S1→S10 flow. Both carry an on-diagram note separating
  what is planned from what runs today.
- **Report sections written:** abstract (296 words), six measurable objectives,
  novelty summary, dataset details covering every mandated field, an AWS services
  planning table over 21 services with planned-versus-running stated per service,
  the implementation-progress table, and the contribution matrix.
- **Udit's research-gap analysis** for papers 1–5.
- `docs/make_docx.py` converts each Markdown deliverable to the `.docx` filename
  the guidelines name, embedding both diagrams in the report. Markdown stays the
  source of truth; the `.docx` files are regenerated artefacts.
- `LICENSE` added (MIT).
- Gates green after the additions: ruff check, ruff format --check, mypy.

Still open: the slide deck itself (`presentation/outline.md` written), Manya's and Tanmoy's research-gap documents,
archiving `uditdaftary/KGCR`, and the `develop`-as-default / `main`-protection
repository settings.

---

## 0. 2026-07-29 — Phase-I realignment

The project was re-based onto the BCSE355L Phase-I guidelines (Dr. Priya V,
deadline 30 July 2026).

- Repository re-created as `KGCR_Cloud_Project_2026` (guideline naming format
  `ProjectName_Cloud_Project_2026`), **seeded with the full 23-commit history**
  of `uditdaftary/KGCR` rather than started empty — commit history is a graded
  artifact. `master` was pushed as `main`.
- Branch topology created per the guidelines: `main` ← `develop` ←
  `feature/udit` | `feature/manya` | `feature/tanmoy`. Manya's and Tanmoy's
  branches are scaffolding for them; all work recorded here is Udit's.
- `CLAUDE.md` added — the submission facts, mandated tree, branch workflow,
  required report sections, citation rules, and hard rules distilled from the
  guidelines PDF.
- This file renamed `logs.md` → `CHANGELOG.md`; contents otherwise unchanged.
- **Tree restructured** to the mandated layout: `kgcr/` → `src/backend/kgcr/`,
  `environment/` → `src/aws/`, `artifacts/` → `results/`, roadmap files parked in
  `docs/`; `architecture/`, `dataset/{raw,processed}/`, `presentation/`,
  `src/frontend/`, `src/ml_model/` created. No code was rewritten — the package
  moved whole and setuptools, mypy, and ruff's isort were pointed at
  `src/backend` (`where`, `mypy_path`, `src`). Without the ruff `src` setting,
  `kgcr` grades as third-party and every test file reports I001.
- `src/ml_model/{preprocessing,train,predict}.py` added — the entry points the
  guidelines name, as thin wrappers over `kgcr.reconstruction`. The library keeps
  the logic and its tests; the wrappers only parse arguments and print. Running
  `train.py` surfaced one real bug: `→` in a print statement raises
  `UnicodeEncodeError` under the Windows console's cp1252 encoding. Output is
  ASCII now.
- `src/frontend/` is a stub with a Phase-II scope note; Phase-I's interface is
  the CLI.
- Quality gates re-run after the move and green: ruff check, ruff format --check,
  mypy (31 files), pytest (130 passed).
- P8 re-run end-to-end through the new entry points on the 180-estate corpus at
  the default seed. Reproduces the recorded result: `iam_shape` accuracy 0.417,
  ECE 0.282; structurally-encoded axes at 1.000 with ECE ≤ 0.052. Report
  committed at `results/reconstruction_report.json`.
- `MIGRATION_PLAN.md` records the gap analysis and the remaining steps: the
  15-paper literature survey (**all 15 need fresh sourcing** — none of the 33
  references in PMD §15 satisfies both the venue and the 2023–2026 filter), the
  two mandatory architecture diagrams, dataset details, `LICENSE`, and report
  assembly.
- `uditdaftary/KGCR` still to be archived as reference-only.

Sections 1–7 below describe the code as of 2026-07-24 and remain accurate; paths
in them were updated to the new tree.

---

## 1. Progress snapshot

| Phase | Title | Status | Where |
|---|---|---|---|
| **P0** | Foundation & reproducibility spine | **Done** | `src/backend/kgcr/{repro,hashing,runrecord,versions,cli}.py`, `src/aws/`, CI |
| **P1** | Ontology encoding (L1) | **Review tools built; no control signed off.** Six drafts, unverified; normative content is human-authored by rule (FD-07 §2) | `src/backend/kgcr/dashboard/authoring.py` |
| **P2** | Gold set | **Register built, no sign-offs** — hand-authored + instructor review is a human act | `src/backend/kgcr/gold/` |
| **P3** | Intent-first generator & Corpus A | **Done** | `src/backend/kgcr/corpus/` |
| **P4** | Labelling (weak supervision) | **Partial** — Checkov and Trivy engines, three-engine agreement, the empirical DF-7 gate, Corpus D coverage; no label model | `src/backend/kgcr/labelling/`, `src/backend/kgcr/adversarial/` |
| **P5** | Defect taxonomy & DF-7 test set | **Done** | `src/backend/kgcr/defects/` |
| **P6** | Advisor & iteration loop | **Done; live run recorded once**: sycophancy gate PASS on 3 valid trials (1 invalid), 2 of 4 variants found, 1 false CRITICAL on 4 clean estates; L1 is a draft pending review; 7 variants unrecorded (quota) | `src/backend/kgcr/advisor/` |
| **P7** | Recommender | **Done**: RF ranker plus CRITICAL mask. A GNN ablation (`results/gnn_ablation.json`) scored a little higher on exact-set recovery and its edge-free control nearly equalled it | `src/backend/kgcr/recommender/` |
| **P8** | Intent reconstruction | **Done** (structural-feature baseline) | `src/backend/kgcr/reconstruction/` |
| **P9** | Explainer | **Done (templates)**: exact paths, evaluated counterfactuals, INV-2 test, design justifications, automated FD-06 evaluation | `src/backend/kgcr/explainer/` |
| **P10** | Agents & end-to-end | **Local end to end done** (`kgcr review`, `design`, `plan`, `apply`); S3/SNS adapters on moto; Config harvest adapter and Terraform-backed apply built against fakes, **never run on AWS** | `src/backend/kgcr/{orchestration,design,plan,apply,harvest}/`, `src/aws/` |
| **P11** | Evaluation & human study | Automated half done (`results/explainer_report.json`); the human study is blocked on ethics approval and participants | — |
| **P12** | Write-up | Not started | — |

Test suite: **474 tests passing** on this machine (Python 3.14.3) as of 2026-10-14. The per-package
counts that used to be listed here went stale as packages were added; `pytest --co -q` has them.

---

## 2. Implemented components

### P0 — reproducibility spine (`src/backend/kgcr/`)
- `repro.py` — `seed_everything` fixes every RNG in reach; `hash_seed_is_fixed`.
- `hashing.py` — `canonical_json` / `canonical_hash` (sorted-key, byte-stable).
- `runrecord.py` — `RunRecord`, identity = hash of `(spec_hash, graph_version, model_version, seed)`; timestamp excluded so identity is what determines the result.
- `versions.py` — environment version fingerprint.
- `cli.py` — the `kgcr` command surface: `repro-info`, `review`, `design`, `plan`, `apply`, `history`, `explain`, `corpus`, `dashboard`.

### P3 — corpus (`src/backend/kgcr/corpus/`)
Intent-**first** generation (FD-05 §4A): sample intent, then render a clean estate, so every estate carries its originating intent as free ground truth.
- `intent.py` — the intent space: `Archetype`, `AZSpread`, `NetworkLayout`, `LoggingPosture`, `IAMShape`, `TaggingDiscipline`, `Scale`; canonically hashable.
- `sampler.py` — seeded, archetype-conditioned intent sampling.
- `generator.py` — renders a clean estate of real `aws_*` resources; deterministic in `(intent, seed)`.
- `estate.py` / `resources.py` — the estate IR; `to_terraform_json()` emits `.tf.json`.
- `graph.py` — in-memory `EstateGraph` (nodes + `DEPENDS_ON` edges), the Neo4j stand-in.
- `plan_parser.py` — parse real `terraform show -json` into the same graph.
- `splits.py` — estate-level (seed-family) train/val/test split with a leakage guard (FD-05 §9).
- `pipeline.py` — sample → render → graph → manifest.

### P5 — defect injection (`src/backend/kgcr/defects/`)
- `taxonomy.py` — `DefectClass` DF-1…DF-7, `Severity`, control URIs (FD-07 `kg://` scheme), `DefectInstance` ground truth (class, site, control, expected finding, evidence path).
- `detectors.py` — a minimal single-resource oracle written from CIS/Checkov rule semantics (silent on the clean corpus) + a bounded graph traversal (`relational_path_exists`).
- `inject.py` — DF-1…DF-6 single-resource property injectors + DF-7 relational path injectors: `indirect_internet_reachability`, `transitive_trust_chain`, `privilege_escalation_passrole`. DF-7 wires individually-compliant resources into a ≤3-hop path, gated on a sensitive sink (cardholder/PII).
- `pipeline.py` — inject across a corpus, the DF-7 (Relational) split, manifest, and `verify_df7_gate` (by-construction invariant: DF-7 estates carry zero single-resource findings yet are graph-recoverable).
- `adversarial.py` — licence-enforcing registry for corpus D. The repositories are now acquired and parsed (`kgcr.adversarial`, `src/ml_model/acquire_corpus_d.py`).

### P4 — labelling (`src/backend/kgcr/labelling/`)
- `checkov_engine.py` — Checkov as a static labelling function, invoked as a subprocess over resource-only `.tf.json`; pure `parse_checkov_json`; `resource_verdict`.
- `df7_contrast.py` — the empirical DF-7 gate: per DF-7 estate, **(a)** the graph recovers the path while **(b)** Checkov's verdict for the (pre-existing, unmutated) sink is byte-identical to the compliant parent. Labeller is injectable for stub-based tests.
- `trivy_engine.py` — Trivy as a subprocess engine (`trivy config`), pure `parse_trivy_json`. `agreement.py` — seeded recall, false positives on the clean parent, percent agreement and Cohen's kappa across the rule floor, Checkov and Trivy. `checkov_engine.run_checkov_on_plan` reads `terraform show -json`, the input on which its single-resource checks are reliable.
- Evidence: `results/p4_df7_checkov_evidence.json`, `results/labeller_agreement.json`.

### Design, plan, apply (`src/backend/kgcr/{design,plan,apply}/`) and the Config harvest
- `design/` — `intake.py` (the eight intent axes, `build_intent`), `extract.py` (grounded free-text extraction, `ExtractionUnavailable`), `synthesize.py` (skeleton from `render_estate`, audit and patch by `OptionRecommender`, `MaskViolation`).
- `plan/` — `local.py` (diff, coverage, blast radius), `cost.py` and `aws_prices.json` (verified list prices, 730 h/month, unpriced items listed), `deployable.py` (the render-time overlay), `terraform_backend.py` (`init`, `validate`, offline `plan`).
- `apply/` — `local.py` (simulated, partial state on failure), `preflight.py` (the plan's resource types against the write role's `provision_services`), `provision.py` (the gated Terraform-backed path, never run).
- `harvest/config.py` — AWS Config adapter with an injected client. Never run against an account.
- `corpus/tfjson.py` — Terraform JSON back into resources. `gold/` — the human-only gold register and the contamination check.

### P8 — intent reconstruction (`src/backend/kgcr/reconstruction/`)
- `features.py` — purely structural feature extraction (reads resources, never the intent).
- `reconstructor.py` — one RandomForest per intent axis, each emitting a value + confidence; region is passed through as directly observed.
- `evaluate.py` — per-field accuracy + per-field calibration (reliability bins + ECE), reported per field, never pooled.
- `pipeline.py` — fit on train+validation, evaluate on the held-out test split.

---

## 3. Key empirical results

- **DF-7 gate, empirical (P4 × P5):** over 12 DF-7 estates (4 estates × 3 variants), the graph recovers **all 12** paths while Checkov — including its CKV2 graph checks — is blind to the sink on **all 12** (verdict byte-identical to the clean parent). C1 holds for every variant. This closes the empirical half of the gate that P5 could only assert by construction.
- **Recommender (P7), 180-estate synthetic corpus, held-out n_test = 24.**
  Options are `(resource_type, attribute, value)`, with identity attributes
  excluded. Exact option-set recovery: popularity 0.000, per-archetype
  frequency 0.208, RF on true intent 0.958, RF on P8-reconstructed intent
  0.958. R-precision for the same four: 0.858, 0.940, 1.000, 1.000. P@10 is
  1.000 for every ranker: about 18 of 44 candidates are relevant per estate, so
  it saturates. The generator is a deterministic function of intent, so this
  measures recovery of the generator's mapping, not real-world recommendation
  quality. The mask removes the one CRITICAL option in the pool
  (`aws_db_instance.storage_encrypted=False`) even when it is forced to rank 1.
  Nested options (ingress blocks, policy documents) are outside the option space
  and are left to the advisor.
- **Advisor (P6), rule floor only, 180-estate synthetic corpus.**
  - Seeded recall is 1.000 for DF-1 to DF-4. This holds by construction: the
    injectors produce exactly what the rules check, so treat it as a sanity
    floor, not a benchmark.
  - Seeded recall is 0.000 for DF-5, DF-6 and DF-7 (n = 64, 180 and 302). These
    are outside the rule floor and are what the LLM path exists for.
  - Clean estates raise 0 CRITICAL findings.
  - One live run (16 Gemini calls, recorded in `results/llm_fixtures/`): the sycophancy gate is
    **PASS** on 3 valid trials (the fourth, `privilege_escalation_passrole`, is invalid: nothing
    raised on pass 1); recall beyond the rule floor is 2 of 4 variants; 1 false CRITICAL on 4 clean
    estates; all 6 proposals grounded. Four trials, one seed: it shows the protocol works, not a
    rate.
- **Corpus D, TerraGoat and CloudGoat:** the rule floor's families cover 31 of 787 Checkov failures (CloudGoat, 740 AWS resources) and 5 of 215 (TerraGoat, 63). Agreement with Checkov where values are readable; misses where an argument is an unresolved expression. No per-resource labels: agreement and coverage only.
- **Three-engine agreement (6 seeded estates per family):** Checkov on plan JSON recalls DF-2, DF-3, DF-4 (6 of 6 each) and not DF-1; Trivy recalls DF-2 and DF-4 and neither DF-1 nor DF-3; no false positives on clean parents. DF-1 is a world-open port 443, which neither engine treats as a defect. Checkov on `.tf.json` recalled 0 of 24.
- **Explainer evaluation (12 bundles):** invariance 12 of 12, counterfactual validity 4 of 4, sparsity mean 0.078 (7 findings), relational Fidelity+ and Fidelity- 1 of 1 each. Small n; most bundles are rule floor only.
- **GNN ablation (99 test estates, four corpus seeds):** exact-set recovery forest 0.941, graph network 0.991, same network without edges 0.984; R-precision and NDCG saturated.
- **Intent reconstruction (P8), 180-estate corpus:** structurally-encoded axes (archetype, network layout, logging, AZ spread) reconstruct at **~100%** and are well-calibrated (ECE ≤ 0.05). `iam_shape` — which the generator leaves no structural trace of — is both least accurate (**~0.42**) and most miscalibrated (**ECE ~0.28**, overconfident at ~0.70). That overconfidence-on-no-signal is the calibration story the reliability diagram exists to surface, and the reason confidence is reported, not just accuracy.

---

## 4. Processes

### Development workflow
- **Branch → PR → merge.** Feature work lands on a `claude/*` branch, opened as a PR against `master`, and merged there. Never commit feature work directly to `master`.
- **Conventional commits**, one logical change each. No AI co-author / "Generated with" trailers (per the working-style instruction).
- **Spec-driven.** Every module cites the FD document that governs it (FD-01…FD-08); the roadmap phase gates define "done".
- **Advisor consulted** before committing to an approach and before declaring a phase done; findings acted on (e.g. the DF-7 measurement was reframed to the non-circular sink-invariance test after review).

### Quality gates (must run and pass before any "done" claim)
Run exactly as CI does, with `PYTHONHASHSEED=0`:
```
ruff check .
ruff format --check .
mypy
pytest
```
- `mypy` is `--strict` over the `kgcr` package (config `packages = ["kgcr"]`); it does not type-check `tests/`.
- CI matrix: Python 3.11 and 3.12.

### Dependencies (pinned per phase)
- Base runtime: `PyYAML` only.
- `dev` extra: pytest, ruff, mypy, types-PyYAML, **and `kgcr[reconstruction]`** (numpy + scikit-learn) so CI gates P8.
- `reconstruction` extra: `numpy==2.4.2`, `scikit-learn==1.8.0`.
- `labelling` extra: `checkov==3.3.8` — **deliberately not in CI**; it is slow and version-fragile, and its tests skip when it is absent. Trivy and Terraform are binaries, installed with winget here, and their tests skip when absent.
- `adversarial` extra: `bc-python-hcl2==0.4.3` (imported as `hcl2`). `advisor` extra: `google-genai`. `aws` extra: `boto3` (in `dev`, with moto). `gnn` extra: `torch==2.14.1`, outside CI.

### Reproducibility
- Deterministic seeding; canonical hashing; run identity from `(spec_hash, graph_version, model_version, seed)`.
- The corpus, defect corpus, and reconstruction experiment all reproduce from their seeds.
- Live-Checkov results are captured as committed artifacts/fixtures so they persist without re-running.

### Testing conventions
- Standard-library `assert`-based tests, no heavy fixtures.
- External-tool tests are guarded (`skipif(not checkov_available())`) and backed by a committed JSON fixture + injectable stubs, so the suite is green with or without the tool.

---

## 5. Decisions and deferred items

- **DF-7 is gated on a genuinely sensitive sink** (cardholder/PII). The internal-reporting archetype gets no DF-7, keeping it the low-sensitivity contrast case (FD-05 §3) rather than accumulating spurious CRITICALs.
- **DF-7 measurement is the sink-invariance contrast**, not a class→check_id recall map (which would have been circular). The sink is pre-existing and unmutated, so comparing its Checkov verdict sidesteps incidental nits on the added scaffolding resources.
- **P1 normative content is not machine-authored** (FD-07 §2: a model may read L1, never write it). P5 defects cite control URIs as strings that will resolve once L1 is hand-authored.
- **Deferred in P4:** Prowler (needs AWS) and the weak-supervision label model. Trivy replaced tfsec as the second engine and inter-engine agreement is measured; the fair DF-1…DF-4 baseline uses plan JSON, because Checkov's `.tf.json` path evaluates single-resource checks inconsistently on interpolated configs.
- **P8 is a structural-feature baseline**, not a GNN. Calibration improvement (Platt/isotonic) is the noted upgrade path. torch is only in the optional `gnn` extra.
- **Corpus D is acquired:** shallow read-only clones under the git-ignored `dataset/raw/corpus_d/`, licences read from each repository, commits pinned in `dataset/processed/corpus_d_manifest.json`. flaws.cloud has no Terraform and is recorded as not applicable.

---

## 6. Environment gotchas (recorded in memory)

- **mypy + StrEnum:** mypy 1.13.0 types `list(SomeStrEnum)` as `list[str]`, not `list[TheEnum]`. This broke `src/backend/kgcr/corpus/sampler.py` (6 errors). Fixed by drawing members via `Enum.__members__.values()`, which preserves the member type and definition order. Repo-wide mypy is now green.
- **Windows shell:** `ruff` is not on the Bash PATH (use `python -m ruff`); Terraform and Trivy need `export PATH="$LOCALAPPDATA/Microsoft/WinGet/Links:$PATH"`. Checkov crashes on cp1252 decoding of some repositories unless run with `PYTHONUTF8=1` and `encoding="utf-8"`. Python written through a Bash heredoc loses backslashes and quotes: use a file-writing tool for any source containing them.
- **Terraform plugin cache:** concurrent `terraform init` runs collide on one plugin cache directory on Windows. Run them one at a time, and seed the cache once.
- **Checkov `.tf.json` is fragile:** its `terraform_json` parser rejects the `provider` block (feed it resource-only input), and single-resource `CKV_AWS_*` checks evaluate inconsistently on interpolated configs. Checkov is invoked as a subprocess (`python -m checkov.main -d <dir> -o json --compact --soft-fail`), not imported. The DF-7 result does not depend on any of this (it compares the sink verdict, which is robust to the quirks).

---

## 7. Commit and PR record

PR numbering restarts in this repository. The list below belongs to the archived
reference repo; numbers there do not correspond to numbers here.

### This repository — `KGCR_Cloud_Project_2026`

- PR #1 — `feature/student1` → `develop`, closed automatically by the branch rename
- PR #2 — `feature/udit` → `develop`: Phase-I submission (governance, mandated tree, all report deliverables)
- PRs #6, #8 and #9 are merged into the branch history (see `git log`).
- 2026-10-13 and 14: 24 local commits on `feature/udit` (spec, plan, design, plan, apply, dashboard
  pages, authoring, Corpus D, Trivy, FD-06 evaluation, harvest adapter, recorder, GNN ablation).
  Not pushed; no pull request opened yet.

### Archived reference repo — `uditdaftary/KGCR`

Merged to `master`:
- `Scaffold Phase 0: reproducibility spine, CLI, CI, and environment IaC` (PR #1)
- `Implement Phase 3: intent-first generator and Corpus A` (PR #2)
- PR #3 — `claude/p5-defect-injection` (merge `1847148`):
  - `fix(corpus): preserve StrEnum member type in sampler axis draws`
  - `feat(defects): Phase 5 defect-injection engine and DF-7 test set`
  - `feat(labelling): Phase 4 Checkov labelling and the empirical DF-7 gate`
  - `feat(reconstruction): Phase 8 intent reconstruction and calibration`

Docs (FD-01…FD-08, PMD, README, roadmap) landed earlier as `docs:` commits.
