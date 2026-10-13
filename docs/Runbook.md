# KGCR runbook

How to install, run, demo, and verify the project as it exists today. Everything here ran on
2026-10-13 (Windows 11, Python 3.14.3) unless marked otherwise. The corpus is synthetic and AWS is
represented by local stand-ins; nothing is deployed.

## 1. Workflow at a glance

```
setup ──► gates ──► demo (kgcr review) ──► regenerate results ──► dashboard
  │         │            │                       │                    │
  pip -e    ruff/mypy/   6 stages, ~15-20 s      train_recommender,    results/
  ".[dev]"  pytest       writes runs/<id>/*      run_advisor           dashboard.html
```

The `kgcr review` pipeline (FD-01), in the order it prints:

| Stage | What happens | AWS today |
|---|---|---|
| 1 harvest | Pick a held-out synthetic estate, inject the chosen defect | Local stand-in for AWS Config |
| 2 graph | Build the dependency graph | none |
| 3 intent | Reconstruct intent (P8) with per-field confidence | none |
| 4 recommend | Rank options, apply the hard CRITICAL mask (P7) | none |
| 5 advise | Rule floor + LLM advisor in the bounded loop (P6) | none (Gemini, replay only by default) |
| 6 explain | Write run record, bundle, patched spec, three audience explanations (P9) | Local stand-in for S3 and SNS |

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

## 3. Quality gates

These are what CI runs. Last run: ruff clean, ruff format clean (96 files), mypy clean (51 files),
**207 passed in ~3 min**.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy
$env:PYTHONHASHSEED = '0'; python -m pytest -q
```

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

### 4.5 Known gotchas (checked)

- **Fixtures are keyed to the estate.** Recorded LLM responses exist only for the estates in
  `results/llm_fixtures/`. A variant without one prints `WARNING ... no usable recorded LLM response`,
  runs on the rule floor only, and reports a clean result for relational defects. Example:
  `--variant indirect_internet_reachability` currently returns **"No findings"** (LLM: missing_fixture).
  The README line that says it is "found only with recorded LLM fixtures" is true only for
  `transitive_trust_chain`; fix the README example or record that fixture (needs a live key).
- The `INFO`/`WARNING` log lines go to stderr. In Windows PowerShell 5.1 this surfaces as a
  `NativeCommandError` banner even on success. Check the exit code, not the banner.
- Run IDs are deterministic. Re-running writes into the same `runs/<id>/` directory.
- Changing `--seed` or `--count` changes which estate is held out, which invalidates the fixtures.

### 4.6 Outputs

Under `<out>/runs/<run-id>/`: `run_record.json`, `bundle.json`, `summary.json`, `timings.json`,
`patched_spec.tf.json`,
`explanation_architect.md`, `explanation_auditor.md`, `explanation_learner.md`. The three
explanations differ only in rendering; the conclusions are identical (tested).

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

## 6. Live Gemini runs (spends API budget, opt-in)

```powershell
pip install -e ".[advisor]"
# .env (git-ignored): GEMINI_API_KEY=<key>   KGCR_LLM_LIVE=1
python -m kgcr.cli review --variant indirect_internet_reachability
```

Capped at 24 calls per run, model `gemini-3.7-flash`. Responses are recorded to
`results/llm_fixtures/` and replayed offline afterwards, so commit the new fixture to make the run
reproducible in CI. The key is never written to disk by the tool. Ask before running, since this
costs real API budget.

## 7. AWS targets (opt-in, not exercised)

```powershell
python -m kgcr.cli review --s3-bucket <bucket> --sns-topic-arn <arn>   # needs ".[aws]" and credentials
```

Tested only against moto. The Terraform in `src/aws/` (budget alarms, cross-account read/write
roles) is authored, not applied. Planned, not working: `design`, `plan`, `apply`.
Working: `history` and `explain` read stored runs back; `dashboard` serves them locally.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `kgcr: command not found` | Scripts dir not on PATH | `python -m kgcr.cli ...` |
| `ruff`/`mypy` not recognised | Same | `python -m ruff`, `python -m mypy` |
| `No findings` on a DF-7 variant | No recorded fixture for that estate | Use `transitive_trust_chain`, or record one (section 6) |
| `no held-out estate admits variant` | Estate set cannot host that defect | Different variant, or change `--seed` and re-record fixtures |
| Results differ between runs | `PYTHONHASHSEED` unset | Set it to `0` |
| `torch seeded: False` in `repro-info` | torch not installed or used yet | Expected |

## 9. What this runbook has and has not verified

Ran and passed on 2026-10-13: all four gates, the 4.1, 4.2 and 4.3 demos, the `indirect_internet_reachability`
demo (clean, as noted), the dashboard build. Not run: live Gemini, anything
against real AWS, `train.py` and `run_advisor.py` regeneration.
