# Design, plan and apply, plus the two authoring tools: design spec

Status: **draft for Udit's review**. Nothing described here is built yet. Written 2026-10-13 on
branch `develop`; the build happens on `feature/udit`.

Governing documents: [FD-01](../../FD-01_Unified_Flow_Specification.md) (flow, invariants),
[FD-02](../../FD-02_Advisor_Iteration_Policy.md), [FD-06](../../FD-06_Explainer_Specification.md),
[FD-07](../../FD-07_Ontology_Specification.md) (L1 authored by humans),
[FD-08](../../FD-08_Environment_Build.md). Where this file and the FD set disagree, the FD set wins
and this file says so below.

---

## 1. What was asked, and what was chosen

Request: "prepare and make all the unbuilt features yet and add them to the dashboard
consecutively; make a spec to map everything out first."

Choices made in the scoping round:

| Question | Answer |
|---|---|
| Scope | **Lazy**: turn on `kgcr design`, `kgcr plan`, `kgcr apply` and their dashboard pages. |
| How far does apply go | **Also a Terraform-backed path**, in addition to a local simulated apply. |
| P1 and P2 (human-authored by rule) | **Authoring tools in the dashboard.** Udit writes the content; no model writes it. |

The authoring tools are outside the "lazy" list but were chosen explicitly, so they are in scope.
Everything else on the unbuilt list is out of scope and stays visible on the dashboard as blocked
(section 9).

## 2. What exists today (verified 2026-10-13)

- `kgcr design`, `plan`, `apply` are stubs that exit 3 ([cli.py:39](../../../src/backend/kgcr/cli.py)).
  The dashboard Commands page lists them as "Not built".
- Review mode runs end to end ([orchestration/review.py](../../../src/backend/kgcr/orchestration/review.py)):
  estate, graph, reconstructed intent, recommender with a CRITICAL mask, advisor loop, explainer,
  stored artifacts. The explainer explains **findings**; a spec with no findings gets an empty bundle.
- `Estate.to_terraform_json()` ([estate.py:45](../../../src/backend/kgcr/corpus/estate.py)) emits a
  provider block (region only) and `required_providers aws ~> 5.60`. Nothing reads `.tf.json` back
  into resources, and `Estate` has no `from_dict`.
- Terraform is **not installed** here (`where terraform` finds nothing). The Terraform in
  `src/aws/` has never been validated ([CHANGELOG](../../../CHANGELOG.md)).
- Generated estates are written for the detectors, not for deployment. In a rendered payments
  estate, `aws_lb.api` has no subnets and `aws_db_instance.cardholder` has no credentials. Neither
  would apply as written.
- The write role `KGCRProvisionApply` ([iam_cross_account.tf:79](../../../src/aws/iam_cross_account.tf))
  grants only `ec2:*`, `s3:*` and `iam:PassRole`, scoped to `var.provision_resource_types`. It is
  created only when `enable_provision_role` is true (default false). Generated estates also contain
  RDS, KMS, ELB, IAM roles and policies, and Glue.
- Fixture replay is keyed by label **and** `prompt_sha256` ([llm.py:136](../../../src/backend/kgcr/advisor/llm.py)).
  A mismatch raises `StaleFixtureError`, which the advisor turns into a rule-floor-only pass. A
  design estate whose id equals a corpus estate id therefore cannot be fed a wrong recorded answer.
  No id salting is needed.
- The advisor prompt contains the control `control_node` and `summary` text. Editing a summary
  changes the prompt hash and invalidates every recorded fixture. `_graph_version()` hashes the whole
  controls file, so even a `verified` flip changes the graph version.
- `CHANGELOG.md` LOOP_STATE says the sycophancy gate is NOT RUN. `results/advisor_report.json` and
  the README say it ran once and passed. The CHANGELOG is stale and is corrected in slice 5.
- No test pins the artifact set or the summary key set, so additive changes to a run are safe.
  `tests/dashboard/test_runstore.py` asserts specific summary keys but not the absence of others.
  Byte-equal `explain` is asserted through `bundle_json(ExplanationBundle.from_dict(...))`.

## 3. Scope

### In

| Item | FD source | Notes |
|---|---|---|
| `kgcr design` | FD-01 S1a, S2 to S5 | Structured intake, not natural language. See 4.1. |
| `kgcr plan` | FD-01 S9 | Local diff always. Terraform backend for design runs. |
| `kgcr apply` | FD-01 S10 | Local simulated apply; Terraform-backed path, authored and never run. |
| Controls review tool | FD-07 section 2 | Records Udit's decisions; writes nothing the advisor reads. |
| Gold set register | FD-05 4C, FD-07 section 12 | Records hand-authored configs; runs the rule floor as the acceptance check. |
| Dashboard pages for all of the above | PRODUCT.md | Reuse the approved Catalog Sleeve system. |

### Out (explicitly)

| Item | Why |
|---|---|
| S6a differential analysis, S7 disposition, T2 ATTESTED, T4 ABORTED | Lazy pick. |
| S8 acceptance gate and edit path, so **INV-6 does not apply** | No edit path is built. |
| S11 feedback commit and FD-03 metrics | Lazy pick. |
| Natural-language intent extraction (`--intent "<statement>"`) | Needs live Gemini, cannot be verified offline, and FD-01 forbids silent defaulting. Structured intake needs none of that. |
| `--budget` and the plan's cost delta | The repo holds no price data. Showing a number would be fabrication. Shown as "not built". |
| Live AWS harvest (`review --account`), live Gemini recordings for the other 7 variants, human study, Corpus D, second labeller, GNN | Blocked by AWS, spend, ethics or data acquisition. Listed on the dashboard with what unblocks each. |

### Invariants

| Invariant | Status in this build |
|---|---|
| INV-1 no spec with an unresolved CRITICAL reaches plan | **Enforced** in `plan`. |
| INV-2 audience changes rendering only | **Kept**; extended to the new design justification (D1) with the existing claim-extraction test. |
| INV-3 no apply without a plan in the same run | **Enforced** in `apply`. |
| INV-4 one terminal state, one run record | **Partial.** Each run writes one run record. Terminal states are not modelled beyond T3 (already exists), T5 (plan exists, no apply) and T1 (applied). Not claimed as complete. |
| INV-5 only Agent 1 holds write credentials | **Enforced** by construction: one module builds a write session; a test asserts nothing else imports it. |
| INV-6 edited specs re-enter review | **Not applicable** (no edit path). |
| INV-7 advisor never sees the recommender's trace | **Kept**; the existing prompt test is extended to design runs. |

## 4. Design

The build is five slices. Each is a backend module with tests, then the CLI command, then the API
route and job, then the dashboard page, then a commit. Gates run between slices.

### Slice 0: groundwork

Small, additive changes the later slices share.

- **Run `mode`.** `summary.json` gains `"mode": "review" | "design"`. Absent means review, so old runs
  read unchanged. `runstore.list_runs` returns `mode`; the History and Run sleeve views branch on it.
- **Observed spec stored.** Review runs also store `observed_spec.tf.json` (the estate as harvested,
  before the advisor loop patches it). Without it a review run has no plan baseline. Runs stored
  before this change have no such file; `plan` refuses them with "re-run the review".
- **`lifecycle.json`.** An append-only event list per run: `designed`, `planned`, `apply_started`,
  `applied`, `apply_failed`, each with a timestamp and the plan id where relevant. This is how plan
  and apply state is shown without touching `RunRecord` identity.
- **Terraform JSON loader.** `resources_from_terraform_json(doc) -> tuple[Resource, ...]`, the inverse
  of `to_terraform_json`: `${a.b.id}` interpolations become `__ref__<arg>` attributes and
  `references`; `depends_on` becomes `references`. A round-trip test over generated estates guards
  it. It returns resources only, because the ground-truth `Intent` cannot be recovered. Plan and the
  gold register both use it.
- **CHANGELOG** corrected in place at slice 5 (sycophancy gate).

### Slice 1: `kgcr design` (dashboard KG 013, user side)

**S1a intake.** The operator supplies all eight `Intent` fields (the seven enum axes plus region).
Missing or invalid fields make the command exit 2 and list them. That refusal is the elicitation;
nothing is defaulted. The dashboard form requires every field. The Commands page lists
`design --intent "<statement>"` as "not built" with the reason.

**S2 synthesis. The synthesizer is the generator skeleton, audited by the recommender.**
`render_estate(intent, seed)` produces the topology, because in this corpus the topology is a
function of the intent. The fitted `OptionRecommender` then ranks and masks options for the same
intent:

- options scoring 0.5 or higher that the skeleton lacks, on a resource type the skeleton has, are
  applied as attribute patches (the `TemplatePatcher` mechanism);
- options the skeleton lacks on a resource type it does not have, and options the skeleton has that
  score under 0.5, are reported and not applied (adding a resource needs references the option does
  not carry);
- if the skeleton contains an option the CRITICAL mask would remove, design fails loudly (INV-1).

**What this does and does not show.** The recommender recovers the generator's mapping at 0.958
exact option-set recovery ([CHANGELOG section 3](../../../CHANGELOG.md)), so on this synthetic corpus
the skeleton and the recommender agree almost by construction. `design` demonstrates the pipeline
and its guarantees. It is **not** independent evidence of recommendation quality, and the page, the
report and the CLI output say so.

**S3 to S5.** The existing advisor loop runs on the candidate. Replay has no recorded response for a
new design estate, so the advisor reports `missing_fixture` and runs the rule floor only, and the
run is labelled exactly that (the `llm_mode` banner already exists). Admin live mode can record real
reviews. The graph is built and the bundle stored as for review runs. The final stage line prints
`stored bundle: ...runs/<16 hex>/bundle.json`, which is how the job runner links a job to its run
([jobs.py:463](../../../src/backend/kgcr/dashboard/jobs.py)).

**D1, design justification (decision for Udit).** The explainer today explains findings, so a clean
design would store an empty bundle and `design` could not "justify every choice" (the README's
claim and C3). If D1 is **in**:

- The bundle gains an optional `justifications` list. Each entry is a control-bearing choice: the
  element and chosen value, plus the alternatives the recommender knows for that attribute whose
  `option_findings` introduce a finding, with the control, severity and defect class of each.
  Choices whose alternatives carry no finding are counted, not narrated ("N further choices are not
  constrained by the controls in scope").
- `bundle_json` writes the key **only when non-empty**, so every stored review bundle still
  round-trips byte for byte.
- Audience renderings reuse `render`; `extract_claims` over the three renderings must be equal
  (INV-2 test extended).
- The consequence shown is the severity of the violated control. **No cost consequence** is shown.

If D1 is **out**, design stores an empty-findings bundle and the page says the justification layer
is not built.

Files: `kgcr/design/` (intake validation, synthesis, patch report), `explainer/explainer.py`
(justifications), `cli.py`, `orchestration/` (`run_design`), tests under `tests/design/`.

### Slice 2: `kgcr plan` (dashboard KG 014, user side, panel one)

`kgcr plan --spec <run-id prefix> [--backend local|terraform]`. Output is an immutable plan under
`runs/<id>/plans/<plan_id>/plan.json`, where `plan_id` is the first 16 hex of
`canonical_hash({spec_hash, baseline_hash, backend})`.

**Refusals (INV-1).** The plan is refused when the run's loop ended `CONTESTED` or any CRITICAL
finding remains in the final pass. Most DF-7 review runs will therefore be refused, which is correct
and is shown with the reason, not hidden.

**Local backend (default).** Baseline is empty for a design run (everything is a create) and
`observed_spec.tf.json` for a review run. The plan reports:

- creates, destroys, and modifies with the attribute-level before and after;
- control coverage before and after: single-resource rule-floor findings by control and severity on
  baseline and on the spec, via the loader and `resource_findings`;
- blast radius: for each modified or destroyed address, the transitive dependents in the dependency
  graph;
- cost delta: **"not built"**.

**Terraform backend (design runs only).** Writes `main.tf.json` and runs `terraform init`,
`terraform plan -out=tfplan`, then `terraform show -json tfplan`, parsed with the existing
`corpus/plan_parser.py`. Against an empty state it can only plan creates, so it is refused for review
runs (a remediation plan needs the live account's state, which is the unbuilt harvest). The runner is
injected, so tests use a fake. **It is authored and never run here**: whether generated specs pass
`terraform validate` is unknown until someone with the binary runs it, and the dashboard says so.
The first real run is a verification step for Udit, not for this build. The control is disabled when
`terraform` is not on `PATH`, as the AWS form is disabled without boto3.

### Slice 3: `kgcr apply` (dashboard KG 014, panel two)

`kgcr apply --plan <plan_id> [--backend local|terraform]`.

**INV-3.** Apply takes a plan id, loads that plan, and recomputes the spec hash from the stored
spec. A mismatch refuses. The Terraform backend applies the **saved planfile**
(`terraform apply tfplan`) and never re-plans, so what is applied is what was reviewed.

**Local backend (default, open to both roles).** A simulated deploy into the artifact store:
`runs/<id>/applied/<plan_id>/state.json` records the resources "created". A failure partway writes
the partial state and an `apply_failed` event (FD-01 S10). Tests inject a failure to prove it.

**Terraform backend (admin only, authored, never run).** Every gate must pass, in this order:

1. Admin session and live mode on (the existing switch; the `terraform` backend counts as a cloud
   target for `validate()`).
2. `terraform` on `PATH`.
3. **Permission preflight.** Every resource type in the plan must belong to a service the write role
   grants. The grant is `ec2`, `s3` and `iam:PassRole`; a constant mirrors it, and a test parses
   `src/aws/iam_cross_account.tf` and fails if the two drift. Offenders are listed and the apply is
   refused. **As the role ships, every generated estate is refused** (KMS, RDS, ELB and IAM
   resources fall outside it). Widening the role is a security setting and Udit's decision; this
   build does not touch it.
4. Typed confirmation: the full plan id.
5. A required acknowledgement that the `src/aws/budgets.tf` alarms are applied (FD-08).
6. Account allow-list: `KGCR_APPLY_ACCOUNT_ID` must equal the account returned by the assumed role's
   caller identity. The role ARN and external id come from environment variables and are never
   logged or written.

The state file lives at `runs-local/tf/<plan_id>/terraform.tfstate`. The apply record stores that
path and the teardown command, which the dashboard displays and **never runs**. Rollback semantics
stay deferred (FD-01 D5).

Even with every gate passed, the generated estates would fail partway (the LB has no subnets, the DB
no credentials). The preflight keeps that from being reached silently. Making generated specs
deployable is generator work and is not in this build.

INV-5: one module (`kgcr/apply/provision.py`) builds the write session. A test asserts that no
other module imports it.

### Slice 4: authoring tools (admin side)

Both tools follow FD-07 section 2: **a model may read L1 but never write it.**

**Rule for this build, binding on the agent doing the work:** no code path, test or manual call may
invoke a review or sign-off endpoint with data a model produced. Tests use fixtures that are
plainly labelled as fixtures and never write to a real database file.

**Controls review (extends KG 024).**
- Per control: `verified`, `needs change` or `rejected`, a note, an optional proposed summary
  text, and the reviewer's name.
- Stored append-only in `dashboard.sqlite3` (`control_reviews`). The current state of a control is
  its latest row. No UPDATE, no DELETE.
- **Export is a browser download**, `controls_review.json`. The dashboard never writes into
  `results/`, so Udit saves and commits the file himself (D3). The sqlite file is git-ignored, so
  without the export the review evidence would never reach the repo.
- The tool **does not touch** `controls_DRAFT-FOR-UDIT-REVIEW.json` or any file the advisor reads.
  Promoting reviewed controls into the advisor's file is a separate, deliberate step that produces a
  new `graph_version` (FD-07 section 10) and, if any summary text changes, invalidates the recorded
  fixtures, which means a paid re-recording. The page states this next to the export button.

**Gold set register (new KG 029).**
- The gold set is 50 to 100 configurations from the Well-Architected Framework, the Security
  Reference Architecture and published financial-services references, compliant by construction and
  **never trained on** (FD-05 4C). It is therefore **not** drawn from the synthetic corpus.
- An entry holds a title, framework and source reference, the configuration as Terraform JSON, the
  controls it exercises, the author, and a status: `draft`, `authored`, `instructor reviewed`.
  Instructor sign-off freezes the entry; changes then need a new entry.
- **Acceptance check** (FD-07 section 12): a button loads the configuration with the Slice 0 loader
  and runs the single-resource rule floor. Any CRITICAL is displayed as "false positive or L1
  encoding error". The check covers single-resource rules only; relational checks need the graph and
  are not claimed.
- Progress toward 50 is displayed from the stored count.
- **Contamination guard:** a test asserts that `kgcr.corpus`, `kgcr.defects`, `kgcr.recommender`,
  `kgcr.reconstruction` and `kgcr.advisor` never import `kgcr.gold`. The register has no code path
  into any training or fitting step.
- Export is a browser download (`gold_set.json`).

### Slice 5: close-out

Commands page moves the three commands to working and lists the deferred items with what unblocks
them. README, PRODUCT.md and the CHANGELOG are corrected in place, including the stale sycophancy
block. Test count in the docs is updated from the real run, not estimated.

## 5. Data written

| Artifact | Where | Notes |
|---|---|---|
| `summary.json` + `mode` | `runs/<id>/` | Additive. |
| `observed_spec.tf.json` | `runs/<id>/` | Review runs only, from slice 0. |
| `lifecycle.json` | `runs/<id>/` | Append-only events. |
| `plan.json` | `runs/<id>/plans/<plan_id>/` | Immutable. |
| `main.tf.json`, `tfplan`, state | `runs-local/tf/<plan_id>/` | Terraform backend only; git-ignored. |
| `apply.json`, `state.json` | `runs/<id>/applied/<plan_id>/` | Local simulated apply and the apply record. |
| `control_reviews`, `gold_entries` | `dashboard.sqlite3` | Git-ignored; exported by download. |

Nothing the dashboard runs writes to `results/` or `dataset/processed/`.

## 6. Dashboard integration

New catalog numbers: **KG 013 New design** and **KG 014 Plan and apply** on the user side, **KG 029
Gold set** on the admin side, and KG 024 renamed **Controls review**. The Run sleeve (KG 011) gains a
lifecycle strip (designed, planned, applied) and links to KG 014. History shows the mode.

New API: `POST /api/jobs` kinds `design`, `plan`, `apply` (the existing allow-list and one-at-a-time
runner); `GET /api/runs/<id>/plans`; `GET|POST /api/authoring/controls`, `GET|POST /api/gold`, and the
two export routes. All writes require a session and `confirm: true` where they sign something off.

**Spend gate unchanged.** Design and plan run in replay mode. The Terraform backend is the only new
spend or cloud path and is behind every gate in slice 3.

**Design rules.** Reuse the approved system in `DESIGN.md` (square corners, hairlines, catalog
numbers, severity colors, yellow for anything that spends). Per your standing rule, a render of
any genuinely new pattern goes to you **before** its UI code: the plan diff table, the lifecycle
strip and the apply confirmation panel before slice 2 and 3 UI, the gold register form before slice
4 UI. I read `~/.claude/standards/design-taste.md` before UI work.

## 7. Verification boundary

| Runs for real | Does not |
|---|---|
| `ruff check`, `ruff format --check`, `mypy`, `PYTHONHASHSEED=0 pytest`, run exactly as CI does, before every commit | Terraform: no binary here. The Terraform path is tested through an injected fake runner only. |
| New pages driven in the built-in browser at 1440 and 390 wide, one design, one plan and one local apply end to end | Real AWS: nothing is applied, assumed into or called. |
| Round-trip, refusal, preflight-drift, contamination and INV tests | Dashboard JavaScript has no lint or test gate. It is verified by driving it, as before. |

Baseline is 207 tests (CHANGELOG), re-run at slice 0.

## 8. What breaks first

1. **Generated specs are not deployable.** The first person to run `kgcr plan --backend terraform`
   with a real binary will meet validation or apply errors on `aws_lb` and `aws_db_instance`. The
   permission preflight blocks apply before that, by design.
2. **Design runs are rule-floor only offline.** Relational checks (DF-7 class) do not run on a design
   unless a fixture exists, so a clean design report is weaker than a clean review report. The banner
   says so.
3. **Old review runs cannot be planned** (no `observed_spec.tf.json`).
4. **Promoting reviewed controls** invalidates fixtures if any summary text changes.

## 9. Blocked items shown on the dashboard

| Item | Unblocked by |
|---|---|
| Live harvest and `review --account` | A deployed AWS Config setup and the read-only role applied |
| Real-AWS apply | Widened write role, deployable generator output, `terraform` installed |
| Recorded Gemini reviews for the other 7 variants | A live-calls decision from you (spend) |
| Human study (P11) | Ethics approval |
| Corpus D, second labeller, GNN | Data acquisition, tfsec or Prowler, torch |
| Natural-language design intake, cost delta | A live-model decision, a verified price source |

## 10. Decisions for Udit

Each has a default; "go" accepts all four.

| | Decision | Default |
|---|---|---|
| **D1** | Add per-choice design justification to the explainer (section 4, slice 1)? It extends the explainer and its invariance test. Without it, `design` stores an empty bundle. | **In** |
| **D2** | Synthesizer: generator skeleton audited and patched by the recommender (section 4, slice 1). The alternative, the generator alone, would leave the recommender decorative. | **Skeleton plus recommender** |
| **D3** | Authoring exports are browser downloads that you commit yourself, rather than server writes into `results/`. | **Download** |
| **D4** | Commit cadence: one commit per slice on `feature/udit` (fast-forwarded from `develop` first), conventional messages, untracked `docs/*.docx` left out, **no push and no PR** until you say so. This spec itself is committed as the first one. | **Per slice, local only** |

---

## 11. Scope change of 2026-10-13 (supersedes sections 1, 3 and 9 where they conflict)

Udit replied "do these and go": install Terraform, complete the blocked tasks, update the
CHANGELOG, let live Gemini run to verify free-text input, and have a Haiku subagent research the
plan's cost data. "Go" accepts **D1 to D4 at their defaults**. The lazy scope in section 1 is
therefore widened. Every item below was on the section 9 blocked list.

The environment check that precedes the build found **no AWS credentials** anywhere (no `AWS_*`
variables, no `~/.aws`). Items that need an account are authored and tested against mocks, and are
reported as not run.

| Item | Disposition |
|---|---|
| Terraform | Installed with winget. Used for `terraform validate` on `src/aws/` (never validated before) and on rendered specs, and for an **offline** `terraform plan` (dummy credentials, provider validation skipped) so the Terraform backend of `plan` is run for real up to the plan. |
| Deployable specs | A **render-time overlay** completes required arguments (LB subnets, DB master credentials via `manage_master_user_password`, instance AMI via a data source) so generated specs pass `terraform validate`. The corpus, its hashes and every recorded fixture stay untouched. |
| Natural-language design intake | **In.** Gemini extracts into the fixed eight-field schema. Each value must carry an evidence span that is a substring of the statement, or the field stays null and design refuses. The operator confirms the form before a run. Verified live once; the response is recorded under `results/llm_fixtures/` so it replays. |
| Plan cost delta | **In.** A Haiku subagent researches official AWS list prices; the main thread re-checks sampled values against the source before they enter the repo. The delta is an on-demand list-price estimate at 730 hours a month, labelled as such, and it lists the usage-dependent items it excludes (data transfer, requests, S3 volume). |
| Recorded Gemini reviews for the other 7 variants | **In.** Live, one process per variant, at most 24 calls each (`KGCR_LLM_LIVE=1` set for that process only; `.env` stays `0`). A 429 is retried by re-running; recorded calls replay. |
| Corpus D | **In.** TerraGoat (and CloudGoat if its licence is on the accepted list) cloned shallow and read-only into an untracked directory, licence read from the repo's own LICENSE file, commit pinned, never executed. HCL parsed with `python-hcl2` (already installed with Checkov). Recall reported with its mapping caveats. flaws.cloud has no Terraform and is recorded as not applicable. |
| Second labeller | **In.** Trivy (the successor to tfsec) as a subprocess engine, mirroring `checkov_engine`, with an inter-engine agreement figure on the DF-1 to DF-4 slice. |
| FD-06 automated evaluation | **In.** Counterfactual validity, sparsity and the cross-audience invariance pass rate, written to `results/explainer_report.json`. Verbalisation fidelity does not apply (explanations are templates, not LLM-rendered). Fidelity+ and Fidelity- are defined for the rule-derived path and reported as exact, not measured. |
| GNN ranker | **Attempted last**, as an optional `gnn` extra outside CI. The expectation, stated before any data, is no gain: the random forest already scores 1.000 R-precision. If `torch` has no wheel for this Python, it is reported as blocked by the environment. |
| Live harvest (`review --account`) | An AWS Config adapter with an injected client, tested against moto. **Not run live: no credentials.** |
| Real-AWS apply | The write role gains an opt-in `provision_services` variable (default unchanged: `ec2`, `s3`); the example tfvars documents the services generated estates need. The permission preflight reads the same list, and the drift test keeps them equal. **No apply is run; this build never assumes a role or calls AWS.** |
| Human study (P11) | **Cannot be completed here.** It needs ethics approval and human participants. Not simulated. |

Mid-build UI note: the new pages are assembled from components already in the approved system
(tables, notices, the spend confirm panel, form fields), so no new scheme is introduced.
Screenshots at 1440 and 390 wide are captured for your review instead of pre-code renders.
