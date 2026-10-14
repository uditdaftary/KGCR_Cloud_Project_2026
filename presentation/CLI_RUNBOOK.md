# CLI screenshot runbook

Run these in order, take one screenshot per step, and paste it over the matching dashed frame in
`KGCR_Final.pptx`. Each frame is 12.1 in wide; the height column gives its size, and the aspect
column is what to crop the screenshot to (width : height) so it fills the frame without rescaling.

Verification boundary: steps 9, 11, 12 and 13 were run on this machine while building the deck, and
their output below is what they printed. The rest are written from `docs/Runbook.md` (run on
2026-10-13 and 14) and the source, and have **not** been re-run for this deck.

## Setup (once, not photographed)

Windows Terminal, PowerShell, from the repository root. A dark theme with a 14 pt monospace font
and a window about 120 columns wide matches the deck.

```powershell
cd C:\Projects\KGCR_Cloud_Project_2026
$env:PYTHONHASHSEED = '0'
Remove-Item -Recurse -Force runs-local\demo -ErrorAction SilentlyContinue
```

Every step writes into `runs-local\demo`, a fresh folder inside the git-ignored `runs-local`, so
`history` is clean, each apply starts unapplied, and the dashboard's own runs are untouched.
Delete the folder when you are done.

The `INFO` and `WARNING` log lines go to stderr. In Windows PowerShell 5.1 they surface as a red
`NativeCommandError` banner even on success. Use Windows Terminal with PowerShell 7 or Git Bash if
you have either, or append `2>$null` to a command to hide the log lines. The stage lines (`[1/6] ...`)
are on stdout and stay.

## Steps

`Slide` is the slide number in `KGCR_Final.pptx`. `Run id` and `plan id` are deterministic; if
yours differ, use the ones the previous command printed.

| # | Slide | Frame h (in) | Aspect | Command | Expected output |
|---|---|---|---|---|---|
| 1 | 18 | 4.5 | 2.7 : 1 | `python -m kgcr.cli --help` | Usage line and the nine subcommands (`repro-info`, `corpus`, `review`, `design`, `plan`, `apply`, `history`, `explain`, `dashboard`) with one-line help. About 20 lines. |
| 2 | 19 | 3.3 | 3.7 : 1 | `python -m kgcr.cli repro-info` | `seed: 1729`, `python_random`, `PYTHONHASHSEED: fixed`, `numpy seeded`, `torch seeded`, then a `tool versions:` list (PyYAML, kgcr, numpy, python 3.14.3, scikit-learn). About 14 lines. |
| 3 | 20 | 5.0 | 2.4 : 1 | `python -m kgcr.cli review --variant unencrypted_database --audience auditor --out runs-local\demo` | Six stages `[1/6] harvest` to `[6/6] explain`, `injected for the demo: unencrypted_database (DF-2)`, `[CRITICAL] kg://control/pci-dss-v4/3.5.1 on aws_db_instance.cardholder (rule)`, loop `CONVERGED (CLEAN)` after 2 passes, remediation `RESOLVED`. About 30 lines, 15 to 20 s. Crop to the stage lines plus the CRITICAL finding. |
| 4 | 21 | 5.0 | 2.4 : 1 | `python -m kgcr.cli review --variant transitive_trust_chain --out runs-local\demo` | `LLM: ok`, `[CRITICAL] kg://control/pci-dss-v4/7.2` on `aws_iam_role.df7_trust_a`, `_b`, `_c`, loop `CONTESTED (OSCILLATING)`, and a `[notification stand-in, not sent]` line. About 30 lines. |
| 5 | 22 | 4.0 | 3 : 1 | `python -m kgcr.cli review --variant no_database_backup --out runs-local\demo` | `LLM: ok`, `[MEDIUM] kg://control/aws-war/reliability-multi-az` on `aws_db_instance.cardholder`, loop `CONVERGED (CLEAN)` after 1 pass. About 22 lines. |
| 6 | 23 | 4.6 | 2.6 : 1 | `python -m kgcr.cli review --variant privilege_escalation_passrole --out runs-local\demo` | `LLM: ok` (replayed), `[CRITICAL] kg://control/pci-dss-v4/7.2` on `aws_iam_role.df7_exec` with the indirect path via `aws_iam_role.priv` to `aws_db_instance.cardholder`, `[MEDIUM]` multi-az on the database, loop `CONTESTED (OSCILLATING)` after 1 pass, and a `[notification stand-in, not sent]` line. About 28 lines. |
| 7 | 24 | 2.2 | 5.5 : 1 | `python -m kgcr.cli history --out runs-local\demo` | Four rows: prefix, timestamp, loop status, finding count, variant (`no_database_backup`, `privilege_escalation_passrole`, `transitive_trust_chain`, `unencrypted_database`). 4 lines. |
| 8 | 25 | 5.2 | 2.3 : 1 | `python -m kgcr.cli explain --run 9d9d36ac --audience learner --out runs-local\demo` | The learner rendering of the DF-7 run: loop outcome `CONTESTED`, the `[CRITICAL]` finding with its `path:` through `df7_trust_a -> b -> c -> cardholder`, the control, and the `if you remove the reference ... RESOLVED` counterfactual, then the MEDIUM finding. About 20 to 25 lines. |
| 9 | 26 | 5.25 | 2.3 : 1 | `python -m kgcr.cli design --archetype payments_api --region eu-west-1 --az-spread two_az --network-layout public_private --logging full --iam-shape least_privilege --tagging strict --scale small --out runs-local\demo` | **Verified.** `[1/5] intake` (8 axes, none defaulted), `[2/5] synthesize  estate fbd0b6698f2ba96e, 15 resources`, `[3/5] graph  15 nodes, 11 dependency edges`, `[4/5] advise  ... CONVERGED (CLEAN)`, `[5/5] explain ... run f0344245b39dd718`, the eight `stored ...` lines, `No findings.`, and `Why these choices:` with the encrypted database and CloudTrail log validation choices. About 35 lines; crop out the `stored` lines if it is too tall. Takes about 20 s. |
| 10 | 27 | 5.25 | 2.3 : 1 | `python -m kgcr.cli design --statement "We are building a payments API that handles card data. It runs in eu-west-1 across three availability zones, with a public load balancer in front of private application subnets, full audit logging, least-privilege IAM roles and strict tagging. Start small." --extract-only` | JSON for the eight axes, each with a value and the quoted evidence (for example `archetype: payments_api` with evidence `payments API`). It replays the recorded Gemini response, so it needs no key. About 40 lines. Only this exact sentence is recorded; any other sentence needs a live key. |
| 11 | 28 | 5.25 | 2.3 : 1 | `python -m kgcr.cli plan --spec f0344245 --out runs-local\demo` | **Verified.** `plan 5102888a2d4cbe21  run f0344245b39dd718  backend local  baseline empty`, `create 15  modify 0  destroy 0`, fifteen `+ aws_...` lines, `findings before: none; after: none`, `cost delta: +50.41 USD a month (list price, priced items only)`, then the `not in the figure:` lines. About 30 lines. |
| 12 | 29 | 3.7 | 3.3 : 1 | `python -m kgcr.cli plan --spec f0344245 --backend terraform --out runs-local\demo` | **Verified.** `terraform 1.16.5 validated and planned offline: 16 creates`, nine `added to make it valid:` lines, two `may still fail to apply:` lines. About 16 lines. Takes one to two minutes (the AWS provider is already cached). |
| 13 | 30 | 3.8 | 3.2 : 1 | `python -m kgcr.cli apply --plan 5102888a2d4cbe21 --out runs-local\demo` | **Verified.** `apply of plan 5102888a2d4cbe21: applied (local, simulated)`, `run f0344245b39dd718`, then fifteen `done     create   aws_...` lines. 17 lines. |
| 14 | 31, top | 1.5 | 8 : 1 | `python -m kgcr.cli apply --plan 5102888a2d4cbe21 --out runs-local\demo` (a second time) | `refused: plan 5102888a2d4cbe21 was already applied`. 1 to 2 lines, exit code 1. |
| 15 | 31, bottom | 1.9 | 6.4 : 1 | `python -m kgcr.cli apply --plan 5102888a2d4cbe21 --backend terraform --out runs-local\demo` | `refused: real applies are switched off (KGCR_APPLY_ENABLED is not 1)`. 1 to 3 lines, exit code 1. |
| 16 | 32, top | 1.6 | 7.5 : 1 | `python -m ruff check .` then `python -m ruff format --check .` then `python -m mypy` (three separate commands, one screenshot) | `All checks passed!`, `164 files already formatted`, `Success: no issues found in 82 source files`. 3 to 6 lines. |
| 17 | 32, bottom | 2.6 | 4.7 : 1 | `python -m pytest -q` | Only the last few lines: `474 passed` and the elapsed time (about 5 minutes). The dots above it are not needed; scroll to the end and crop. |
| 18 | 33 | 3.0 | 4 : 1 | `python -m kgcr.cli corpus --count 180` | `estates: 180`, `unique estate ids`, `seed families`, `total resources: 2331`, `graph nodes / edges: 2331 / 1615`, and the archetype distribution (64 payments_api, 60 internal_reporting, 56 customer_data_platform). About 10 lines. |
| 19 | 34 | 1.6 | 7.5 : 1 | `python -m kgcr.cli dashboard --port 8765 --out runs-local` | One line: `KGCR dashboard on http://127.0.0.1:8765  (replay mode; Ctrl+C to stop)`. Stop it with Ctrl+C after the shot. If a dashboard is already running on 8765, use `--port 8766`. |

## Cleanup

```powershell
Remove-Item -Recurse -Force runs-local\demo
```

## Notes

- Steps 9, 11, 13 share the same run and plan ids on every machine, because run ids hash the spec.
- Step 10 prints nothing useful without the recorded fixture in `results/llm_fixtures/`; the file
  `intent-v1-*.json` for that sentence is in the repository.
- If a screenshot comes out a different shape than its frame, resize it to the frame width and
  centre it. Nothing on the slides depends on the exact frame height.
- The dashboard screenshots in this deck were taken from a dashboard serving `runs-local`, with a
  design, a plan and a simulated apply added through the CLI first.
