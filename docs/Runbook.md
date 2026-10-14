# KGCR runbook

How to install, run, demo, and verify the project as it exists today. Everything here ran on
2026-10-13 and 14 (Windows 11, Python 3.14.3) unless marked otherwise. The corpus is synthetic and
AWS is represented by local stand-ins. **Nothing in this repository has touched a real AWS
account**: the Terraform-backed apply and the AWS Config harvest are built and tested against
fakes only (section 7).

## 1. Workflow at a glance

```
setup ──► gates ──► review ──► design ──► plan ──► apply ──► regenerate results ──► dashboard
  │         │          │          │         │         │              │                  │
  pip -e    ruff/mypy/ kgcr       kgcr      kgcr      kgcr           train_*, run_*     kgcr dashboard
  ".[dev]"  pytest     review     design    plan      apply          scripts            results/dashboard.html
```

Review mode takes an existing estate and asks what is wrong with it. Design mode runs the same
machinery forward: it builds a spec from an intent, reviews it, and hands it to plan and apply.
Every run is stored under `<out>/runs/<run-id>/` and records its `mode`.

The `kgcr review` pipeline (FD-01), in the order it prints:

| Stage | What happens | AWS today |
|---|---|---|
| 1 harvest | Pick a held-out synthetic estate, inject the chosen defect | Local stand-in for AWS Config |
| 2 graph | Build the dependency graph | none |
| 3 intent | Reconstruct intent (P8) with per-field confidence | none |
| 4 recommend | Rank options, apply the hard CRITICAL mask (P7) | none |
| 5 advise | Rule floor + LLM advisor in the bounded loop (P6) | none (Gemini, replay only by default) |
| 6 explain | Write run record, bundle, patched spec, three audience explanations (P9) | Local stand-in for S3 and SNS |

The `kgcr design` pipeline prints five stages: `intake` (the eight intent axes), `synthesize` (a
generator skeleton audited and patched by the option recommender), `graph`, `advise`, `explain`.

## 2. Setup

Requires Python 3.11+. From the repo root:

```bash
pip install -e ".[dev]"
```

On this machine the `kgcr` script is not on PATH (neither Git Bash nor PowerShell). Use the module
form everywhere:

```powershell
$env:PYTHONHASHSEED = '0'
python -m kgcr.cli repro-info      # seed and version fingerprint
```

Bash equivalent: `export PYTHONHASHSEED=0`. Fix once with `pip install -e .` into a venv whose
Scripts directory is on PATH, or keep using `python -m kgcr.cli`.

Optional extras and binaries. None is needed for the demos in section 4; each skips its tests when
absent, and CI has none of them.

| Needed for | Install |
|---|---|
| `kgcr plan --backend terraform`, the labeller comparison | Terraform: `winget install Hashicorp.Terraform` (v1.16.5 here). `kgcr` finds the winget link even when PATH predates it |
| The labeller comparison | Trivy (`winget install AquaSecurity.Trivy`, 0.75.0 here) and `pip install -e ".[labelling]"` (Checkov 3.3.8) |
| Corpus D | `pip install -e ".[adversarial]"` (imported as `hcl2`), then `python src/ml_model/acquire_corpus_d.py` |
| Live Gemini | `pip install -e ".[advisor]"` (section 6) |
| The GNN ablation | `pip install -e ".[gnn]"` (torch). Run it in a throwaway venv |

In Git Bash, winget binaries need `export PATH="$LOCALAPPDATA/Microsoft/WinGet/Links:$PATH"` for
Terraform and Trivy to be found by anything other than `kgcr`.

## 3. Quality gates

These are what CI runs. Last run on the build machine: ruff clean, ruff format clean (164 files),
mypy clean (82 source files), **474 passed in ~5 min** (Python 3.14, with Checkov, Trivy and
Terraform installed). In a fresh Python 3.12 venv with only `pip install -e ".[dev]"` the same
gates are clean and 457 pass, 4 skip (hcl2, google-genai and Checkov absent). CI runs the gates on
3.11 and 3.12 for every push; the pull request's checks are the record of that.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy
$env:PYTHONHASHSEED = '0'; python -m pytest -q
```

Run the four as separate commands: a chained `| tail` hides a failing exit code.

## 4. Run the demo

All commands accept `--out <dir>` (artifact store root, default `runs-local/`),
`--audience architect|auditor|learner`, `--count` (corpus size, default 180) and `--seed`.

### 4.1 Single-resource defect, found by the rule floor (no LLM needed)

```powershell
python -m kgcr.cli review --variant unencrypted_database --audience auditor
```

Expected: `[CRITICAL] kg://control/pci-dss-v4/3.5.1 on aws_db_instance.cardholder (rule)`, loop
`CONVERGED (CLEAN)` after 2 passes, remediation tested and `RESOLVED`. Takes about 18 s.

### 4.2 Multi-hop defect (DF-7), found only with the recorded LLM response

```powershell
python -m kgcr.cli review --variant transitive_trust_chain
```

Expected: `LLM: ok`, `[CRITICAL] kg://control/pci-dss-v4/7.2` on `df7_trust_a/b/c`, loop
`CONTESTED (OSCILLATING)`, and a `[notification stand-in, not sent]` line. This is the C1 claim
in action: a path of individually compliant resources that single-resource rules cannot see.

### 4.3 Resilience defect (DF-5)

```powershell
python -m kgcr.cli review --variant no_database_backup
```

Expected: `LLM: ok`, `[MEDIUM] kg://control/aws-war/reliability-multi-az` on `aws_db_instance.cardholder`, loop `CONVERGED (CLEAN)` after 1 pass. Replays recorded response `v1-9b5b10ffce9c9596`.

### 4.4 Variants

`open_security_group`, `unencrypted_database`, `wildcard_iam_policy`, `cloudtrail_no_log_validation`,
`no_database_backup`, `unattached_volume`, `indirect_internet_reachability`,
`transitive_trust_chain`, `privilege_escalation_passrole`.

A variant that no held-out estate admits raises `ValueError: no held-out estate admits variant ...`.

### 4.5 Design, plan and apply

Design a payments API, plan it, and apply the plan to the local simulation:

```powershell
python -m kgcr.cli design --archetype payments_api --region eu-west-1 --az-spread two_az `
    --network-layout public_private --logging full --iam-shape least_privilege `
    --tagging strict --scale small --out runs-local
python -m kgcr.cli plan --spec <run-id prefix> --out runs-local
python -m kgcr.cli apply --plan <plan-id> --out runs-local
```

Expected, with the arguments above: `[1/5] intake  stated intent, 8 axes, none defaulted`, a
15-resource estate, `Loop outcome: CONVERGED (CLEAN)`, and the run id on the `[5/5]` line. The
plan prints `create 15  modify 0  destroy 0`, `findings before: none; after: none`, and
`cost delta: +50.41 USD a month (list price, priced items only)` followed by a `not in the figure`
line for everything it cannot price (an IAM role, a VPC, load balancer capacity units, S3 volume).
It is never zeroed. The apply lists each create as `done`.

- **Free-text intake.** `design --statement "<sentence>" --extract-only` asks Gemini to fill the
  eight axes. A value is admitted only if it is in the schema and its evidence is a quotation of
  the statement; anything else stays `null`. Without `--extract-only`, `design` prints each axis
  with its evidence as a `[0/5] extract` stage, then stops with exit 2 and the allowed choices if
  any axis is still empty: an unstated requirement is stated by you, never assumed. A flag you
  give always wins over the statement. The statement recorded under `results/llm_fixtures/`
  replays offline; any other statement needs a live key (section 6). The recorded one is in
  `tests/dashboard/test_design_plan_apply_api.py`.
- **Terraform backend.** Add `--backend terraform` to `plan`. It runs `init`, `validate` and a plan
  with mock credentials against the real binary, for design runs only. With the arguments above:
  `terraform 1.16.5 validated and planned offline: 16 creates`, one more than the spec, because the
  overlay adds a DB subnet group. Every completion is listed under `added to make it valid` and
  every remaining problem under `may still fail to apply`. A valid plan does not mean an apply
  would succeed. First use downloads the AWS provider (about 700 MB) into `<out>/tf/.plugin-cache`; one plan
  then takes roughly a minute or two.
- **Refusals are the feature.** A second `apply` of the same plan exits 1 with `refused: plan <id>
  was already applied`. `apply --backend terraform` refuses with `real applies are switched off
  (KGCR_APPLY_ENABLED is not 1)` and has many further gates after that one. No spec with an open
  CRITICAL finding reaches a plan.
- **Plans are immutable.** They live under `runs/<prefix>/plans/<plan_id>/plan.json`; the id hashes
  the spec, baseline, backend and overlay. Applied state is under `runs/<prefix>/applied/`.
- `design` prints `cost delta not modelled: L1 carries no cost facts yet`. That is about the
  review's explanation; the plan carries the cost delta.

### 4.6 Known gotchas (checked)

- **Fixtures are keyed to the estate.** Recorded LLM responses exist only for the estates in
  `results/llm_fixtures/`. A variant without one prints `WARNING ... no usable recorded LLM response`,
  runs on the rule floor only, and reports a clean result for relational defects. Example:
  `--variant indirect_internet_reachability` currently returns **"No findings"** (LLM: missing_fixture).
  Five variants have recordings (`transitive_trust_chain`, `no_database_backup`,
  `privilege_escalation_passrole`, `unencrypted_database`, `open_security_group`) and
  `wildcard_iam_policy` has pass 1 only (`LLM: partial`); the other three are waiting on the Gemini
  quota (section 6). Designs also run rule floor only, for the same reason.
- The `INFO`/`WARNING` log lines go to stderr. In Windows PowerShell 5.1 this surfaces as a
  `NativeCommandError` banner even on success. Check the exit code, not the banner.
- Run IDs are deterministic. Re-running writes into the same `runs/<id>/` directory.
- Changing `--seed` or `--count` changes which estate is held out, which invalidates the fixtures.

### 4.7 Outputs

Under `<out>/runs/<run-id>/`: `run_record.json`, `bundle.json`, `summary.json`, `timings.json`,
`patched_spec.tf.json`, `lifecycle.json`,
`explanation_architect.md`, `explanation_auditor.md`, `explanation_learner.md`, and `plans/` once a
plan exists. The three explanations differ only in rendering; the conclusions are identical
(tested).

## 5. Regenerate results and the dashboard

```powershell
python src/ml_model/train_recommender.py   # results/recommender_report.json
python src/ml_model/run_advisor.py         # results/advisor_report.json
python src/frontend/build_dashboard.py     # results/dashboard.html
```

Rebuild the dashboard after `run_advisor.py`, because it reads gate state from the reports.
`build_dashboard.py` rewrites `results/dashboard.html` in place (one line changes per run), so
`git checkout results/dashboard.html` if you only ran it to look.

Other entry points: `src/ml_model/preprocessing.py` (generate corpus into `dataset/processed/`),
`train.py` (intent model, writes `model.pkl`), `predict.py` (one estate).

Results added with design, plan and apply (each needs the tools in section 2):

| Script | Writes | Notes |
|---|---|---|
| `run_corpus_d.py` | `results/corpus_d_report.json` | Rule floor against Checkov on TerraGoat and CloudGoat. Run `acquire_corpus_d.py` first. Agreement and coverage, not accuracy: the repositories have no per-resource labels |
| `run_labeller_agreement.py` | `results/labeller_agreement.json` | Rule floor, Checkov and Trivy on 6 seeded estates per family. ~25 min: Checkov reads real `terraform show -json` plans. `--checkov-input tfjson --report-out results/labeller_agreement_tfjson.json` reproduces the run where Checkov recalls 0 of 24 |
| `run_explainer_eval.py` | `results/explainer_report.json` | Invariance, counterfactual validity, sparsity, relational fidelity over 12 bundles. About a minute |
| `gnn_ablation.py` | `results/gnn_ablation.json` | A graph network against the forest, with an edge-free control. Needs torch; a few minutes |

Run these from PowerShell or a shell where `python` is the interpreter that has the extras. The
outputs reproduce from their seeds; none is run by CI.

## 5a. The dashboard

```powershell
python -m kgcr.cli dashboard --open        # 127.0.0.1:8765, stdlib only
```

Two roles on the cover, user and admin, with no login by design. The user side runs reviews and
designs and reads the results; it also holds the plan and apply page for each run. The admin side
holds the job queue, the controls review and gold set pages, recorded fixtures, cloud and spend,
and the Commands page, which lists the six things that are not built with what would unblock each.

- **Spend gate.** Every job forces `KGCR_LLM_LIVE=0` and withholds `GEMINI_*` and `AWS_*`. An admin
  can enable live mode (in memory; it resets when the server restarts). A Terraform-backed apply
  is a cloud job: it needs an admin and live mode.
- **Authoring is human-only.** The model may read the controls, never write them. Records are
  append-only, a reviewer is never the author, a CRITICAL comment blocks sign-off, and the gold
  register freezes on instructor sign-off. Exports are browser downloads that a person commits.
- Jobs write to `runs-local/jobs/KG<no>/`, never to `results/`.

## 6. Live Gemini runs (spends API budget, opt-in)

```powershell
pip install -e ".[advisor]"
# .env (git-ignored): GEMINI_API_KEY=<key>   KGCR_LLM_LIVE=1
python -m kgcr.cli review --variant indirect_internet_reachability
python src/ml_model/record_variants.py --budget 18   # every variant that has no recording yet
```

Capped at 24 calls per process, model `gemini-3.7-flash`. Responses are recorded to
`results/llm_fixtures/` and replayed offline afterwards, so commit the new fixture to make the run
reproducible in CI. The key is never written to disk by the tool. Ask before running, since this
costs real API budget.

- **The free tier allows about 20 requests a day.** The quota resets at midnight Pacific (12:30
  local, IST). On 2026-10-13 the quota was spent verifying free-text intake, and a retry of
  `record_variants.py` at 23:36 local was refused with a 429 on its first call.
- `record_variants.py` is idempotent: recorded calls replay for free, so a second run only spends on
  what is missing. It does the relational variants first, stops at the first quota refusal or at
  `--budget`, and keeps what it recorded. Seven variants are still unrecorded.
- A 503 is retried twice (5 s, then 15 s) and then reported; free-text extraction failures surface
  as "unavailable", not as a bad intent.
- Never leave `KGCR_LLM_LIVE=1` in your shell: set it for one process.

## 7. AWS targets (opt-in, not exercised)

```powershell
python -m kgcr.cli review --s3-bucket <bucket> --sns-topic-arn <arn>   # needs ".[aws]" and credentials
```

Tested only against moto. The Terraform in `src/aws/` (budget alarms, cross-account read/write
roles, the run bucket and SNS topic) passes `terraform init -backend=false` and `terraform
validate` under v1.16.5. It has not been planned against an account or applied.

Built, never run on AWS:

- **Terraform-backed apply** (`kgcr apply --backend terraform`). It refuses in order unless real
  applies are switched on (`KGCR_APPLY_ENABLED=1`), the plan and spec hash hold, the plan came
  from the Terraform backend, the binary exists, the write role's grant covers every resource type
  in the plan, the plan id is typed again (`--confirm`), the budget alarms are acknowledged
  (`--budgets-applied`), the image is real (`KGCR_AMI_ID`), the role, external id and account are
  set, the plan was not already applied, and the assumed account matches. It then **re-plans
  against the live provider** and refuses unless the creates equal the reviewed plan: the offline
  plan used mock credentials, so its planfile cannot be applied. Tested against fakes only.
- **The write role covers `ec2` and `s3` by default**, so every generated estate is refused at the
  preflight. `provision_services` in `src/aws/variables.tf` widens it; the example tfvars lists
  what generated estates need. Widening the role is your decision.
- **AWS Config harvest** (`kgcr.harvest.config`). An injected client, five resource types (RDS
  instance, S3 bucket, security group, EC2 instance, KMS key), read-only. Tested against botocore
  stubs and moto. It returns no tags (the batch API strips them) and no networks or IAM, and
  `kgcr review --account` is not wired to it.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `kgcr: command not found` | Scripts dir not on PATH | `python -m kgcr.cli ...` |
| `ruff`/`mypy` not recognised | Same | `python -m ruff`, `python -m mypy` |
| `No findings` on a DF-7 variant | No recorded fixture for that estate | Use `transitive_trust_chain`, or record one (section 6) |
| `no held-out estate admits variant` | Estate set cannot host that defect | Different variant, or change `--seed` and re-record fixtures |
| Results differ between runs | `PYTHONHASHSEED` unset | Set it to `0` |
| `torch seeded: False` in `repro-info` | torch not installed or used yet | Expected |
| `429` from Gemini | Free-tier daily quota spent | Wait for midnight Pacific; re-run `record_variants.py` |
| `terraform validate failed` on a plan | The overlay does not cover an argument the provider requires | The message is Terraform's own; add the completion to `plan/deployable.py` |
| `Failed to install provider ... being used by another process` | Two `terraform init` runs share one plugin cache | Run them one at a time |
| Checkov crashes on `charmap` or `cp1252` | It reads files with the platform encoding | Run it with `PYTHONUTF8=1` (the engine does this itself) |
| Checkov reports nothing for a seeded defect | Its `.tf.json` parser evaluates single-resource checks unreliably | Feed it plan JSON (`run_checkov_on_plan`) |
| `refused: the write role's grant does not cover ...` | Plan creates a type outside `provision_services` | Widen the role deliberately, or do not apply |
| Python written through a Bash heredoc loses backslashes or quotes | Bash tool quoting | Write the script to a file first |

## 9. What this runbook has and has not verified

Ran and passed on 2026-10-13 and 14: all four gates on the build machine and in a fresh Python 3.12
venv; the 4.1, 4.2 and 4.3 demos; the `indirect_internet_reachability` demo (clean, as noted);
section 4.5 end to end (structured design, local plan, Terraform-backed offline plan, local apply,
the second-apply refusal, the gated Terraform refusal, free-text extraction replaying the recorded
statement); `terraform validate` on `src/aws/`; the corpus D, labeller, explainer and GNN scripts
(results committed); the dashboard Commands page and four other routes at 375 px wide, through the
DOM.

Not run: any real AWS call (harvest, apply, the S3 and SNS adapters against an account); live
Gemini beyond free-text intake (the seven variant recordings are waiting on quota); the human
study; instructor sign-off of the controls and gold set; Python 3.11 locally (CI covers it);
browser screenshots of the new dashboard pages (the pane was hidden, so they were driven
through the API and the DOM).
