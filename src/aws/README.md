# `src/aws/` — Phase 0 bootstrap (FD-08 §8) and the run-artifact targets

Terraform that reproduces the [FD-08](../docs/FD-08_Environment_Build.md)
three-account estate using only standalone-account primitives — **no AWS
Organization required** (FD-08 §2–§3). Its purpose is to make the two most
important Phase 0 facts true and un-forgettable:

- **Budget alarms exist on day one** at $5 / $15 / $30 (`budgets.tf`), created
  by code so they cannot be forgotten — the dominant Phase 0 cost risk (FD-08
  §6).
- **The read/write split is structural** (`iam_cross_account.tf`): the harvest
  role holds zero write actions, so INV-5 holds by construction (FD-08 §4.1).

> **Status: authored, not yet applied.** Terraform is not installed in the
> environment where this was written, so it has **not** been run through
> `terraform init/validate/plan`. Treat it as a reviewed starting point:
> validate against real account IDs before applying. Applying it is a live-AWS
> step that belongs to Student A during Phase 0.

## Layout

| File | Contents |
|---|---|
| `versions.tf` | Terraform and AWS provider version pins |
| `variables.tf` | Inputs — account principal, external IDs, thresholds, tags |
| `budgets.tf` | The $5 / $15 / $30 budget alarms (FD-08 §6) |
| `iam_cross_account.tf` | `KGCRHarvestReadOnly` (always) and `KGCRProvisionApply` (demo only) |
| `run_artifacts.tf` | S3 run bucket (private, encrypted, TLS-only, expiring), SNS contested-run topic, least-privilege `KGCRPipelinePublish` policy |
| `outputs.tf` | Role ARNs, budget names, run bucket, topic ARN, publish policy ARN |
| `terraform.tfvars.example` | Template for the (gitignored) `terraform.tfvars` |

## Applying (per account)

Applied once per account, each with its own `terraform.tfvars` and its own state
(a separate workspace or backend key per account — accounts A, B, C):

```bash
cd src/aws
cp terraform.tfvars.example terraform.tfvars   # then edit
terraform init
terraform plan     # review before every apply
terraform apply
```

- **Accounts A, B, C**: budget alarms apply everywhere.
- **Accounts A, B**: the harvest role applies (C is the trusted principal, so it
  does not grant a role to itself).
- **Account A only, demo window only**: set `enable_provision_role = true` and
  populate `provision_resource_types`; set it back to `false` and re-apply to
  remove the write path after the demo (FD-08 §6).

## Not covered here

Out of scope for this skeleton, to be added as the phases that need them arrive:
the S3 landing buckets and ETL wiring in C (FD-08 §5), the Neo4j host, and the
deliberately-flawed reference estate in A (FD-08 §7) — the last is a
separately-applied, separately-destroyed stack so it stays out of steady-state
cost.

## Phase 0 exit gate (FD-08 §10)

This module covers items 1, 2 (creation half), and 4 of the gate. The remaining
items are manual or later: the **test-breach verification** of the alarms, the
**hello-world cross-account read**, and the full **stand-up / tear-down** proof.

## Using the run bucket and topic from `kgcr review`

`kgcr review` stays local by default. Once `run_artifacts.tf` is applied:

```bash
pip install -e ".[aws]"
kgcr review --s3-bucket "$(terraform output -raw run_bucket_name)"             --sns-topic-arn "$(terraform output -raw contested_runs_topic_arn)"
```

The adapters (`S3ArtifactStore`, `SnsNotifier` in `src/backend/kgcr/orchestration/aws.py`) are
tested against moto's in-process AWS mock (`tests/orchestration/test_aws.py`). They have not been
run against a real account.
