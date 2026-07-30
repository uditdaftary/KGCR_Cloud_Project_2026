# FD-08 — Environment Build

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-08
**Status:** Baseline
**Governs:** Phase 0 of the milestone plan — the three-account estate, IAM, cost controls, and the analysis host
**Depends on:** FD-01 (actors, INV-5), FD-03 (governance, graph sensitivity), FD-05 (cost control, corpus-as-plan)
**Resolves:** D7 (topology mapping onto available accounts) — see §3

---

## 1. Purpose

Phase 0 is the substrate every later phase runs on, and its exit criterion — *three accounts wired, alarms live, cross-account read works* (PMD §10) — is the first thing that must be true. This document specifies how the three-account estate (PMD §6) maps onto the accounts actually available to a student project, how the cross-account trust is wired without assuming an AWS Organization, and how the environment is prevented from quietly burning the small credit budget.

The dominant Phase-0 risk is not difficulty; it is **a forgotten always-on service** (FD-05 §10). This document is written to make that failure structurally unlikely, not merely discouraged.

---

## 2. The constraint

Three accounts, no meaningful credit budget, and — the part the architecture originally glossed — **no guarantee those accounts can form an AWS Organization.** AWS Academy / Learner Lab and individually-registered free-tier accounts frequently cannot create or join an Organization, cannot hold a management account, and cannot apply Service Control Policies. The PMD §6 topology names an "AWS Organizations pattern"; taking that literally would block Phase 0 on a capability the accounts may not have.

The resolution (§3) is to reproduce the *intent* of the multi-account landing zone — separation of duties across trust boundaries — using only primitives every account has: standalone accounts and cross-account IAM roles. This is D7, resolved.

**Decision (accepted): the build does not require AWS Organizations.** In practice the three accounts are expected to be the three students' individual sandbox accounts — which cannot generally form an Organization anyway, so the standalone-accounts design is not a fallback here, it is *the* design. AWS Organizations, if ever available, is optional hardening (§3), never a dependency.

---

## 3. Account topology and role mapping (resolves D7)

Three standalone accounts, mapped to the PMD §6 roles:

| Account | PMD role | Contents | Trust posture |
|---|---|---|---|
| **A — prod-payments** | Estate under analysis; harvest target | Reference deployment; the deliberately-flawed reference estate (§7); demo `apply` target | Grants two roles *to* C |
| **B — dev-staging** | Drift comparison | A divergent copy of A | Grants a read role *to* C |
| **C — shared-security** | Analysis platform | Neo4j host, models, CLI host, S3 landing buckets, ETL | Holds the principal that assumes into A and B |

**Wiring, without Organizations.** Account C holds the CLI/analysis principal. Accounts A and B each define IAM roles whose trust policy names C's principal directly (by account ID and role ARN) plus an **external ID**, rather than relying on an Org-level SCP or a management account. Cross-account access is therefore `sts:AssumeRole` into a named role, wired manually. No Organization is required.

If an Organization *is* available, add it as defence in depth (an SCP denying `iam:*` outside the provisioning role, a consolidated billing view) — but nothing in the build depends on it.

**Fallback — single account (§4.2).** If only one account is granted, the three-account topology is simulated within it; a validity limitation follows and must be stated.

---

## 4. Cross-account IAM design

### 4.1 The two roles, and INV-5

INV-5 requires that Agent 2 (Harvester) holds only read credentials and Agent 1 (Provisioner) is the sole writer. This is enforced by **making them two distinct roles with disjoint permissions**, not by trusting a single role to behave:

| Role (in A / B) | Assumed by | Actor | Permissions | Used when |
|---|---|---|---|---|
| `KGCRHarvestReadOnly` | C's principal | **Agent 2** | AWS managed `SecurityAudit` + `ViewOnlyAccess`; `config:Describe*/Get*`, `cloudtrail:LookupEvents`, `iam:Get*/List*`, `ce:Get*`, `s3:GetObject` on the CUR bucket, `tag:Get*`. **Zero write actions.** | Every review run |
| `KGCRProvisionApply` (A only) | C's principal | **Agent 1** | Scoped to the resource types the corpus/demo provisions; write actions on those types only | Demo `apply` only, then torn down |

Because the harvest role contains no write action of any kind, INV-5 holds *by construction* — Agent 2 cannot write even if compromised. Agent 1's role is the highest-risk component in the system (FD-01 §3) and is therefore the most tightly scoped, MFA-conditioned where the account supports it, and enabled only during the demonstration window.

### 4.2 Fallback: single-account simulation

If three accounts are unavailable, simulate the topology in one account:

- Three VPCs (`vpc-prod`, `vpc-staging`, `vpc-security`) and a tag partition `estate ∈ {A, B, C}`.
- Two IAM roles (`KGCRHarvestReadOnly`, `KGCRProvisionApply`) scoped by resource tag, assumed within the one account, preserving the read/write split and INV-5.

**Validity limitation to state:** a single account has no true account-boundary isolation, so cross-account trust findings (a class of DF-3 identity defects) are simulated rather than real. Report this as a scoped limitation, consistent with FD-05 §11's posture on synthetic-data honesty.

---

## 5. Analysis stack and data pipeline

The stack of PMD §6, made concrete and cost-gated:

```
A, B (estates)  ──[cross-account read]──▶  C: S3 landing  ──▶  Lambda/Glue ETL  ──▶  Neo4j Community (L2/L3)
   AWS Config ─┐                                                                         ▲
   CloudTrail ─┼─▶ (only during demo windows, Account C)                                 │
   CUR (Cost) ─┘                                                          L1 authored (FD-07), frozen
```

- **Graph store: Neo4j Community**, single small instance in C, or local for development. **Not Neptune** — it bills continuously and will exhaust credits in days (FD-05 §10). L1 (FD-07) is loaded and frozen; Agent 2 writes L2; the run recorder writes L3.
- **ETL** parses `terraform plan` JSON and harvested Config snapshots into the graph. For the corpus, this is the *only* path that runs — nothing is deployed (§6).
- **CLI host** in C runs `kgcr`; it holds the principal that assumes the A/B roles.

---

## 6. Cost governance

This section is authoritative for the project's spend posture; FD-05 §10 introduced it, this document owns it.

| Control | Action | Rationale |
|---|---|---|
| **Budget alarms** | AWS Budgets on **day one**, at **$5 / $15 / $30**, on **all three accounts**, alerting to email | Not after the first surprise. The single most important line in this document. |
| **Corpus generation** | `terraform plan` only; parse plan JSON. **No `apply`.** | The corpus is IaC artifacts, not running infrastructure (FD-05 §10). Nothing to bill. |
| **Continuously-billing services** | AWS Config recorders, Security Hub, GuardDuty enabled **only in Account C, only during demo windows**, disabled immediately after | These bill per-resource per-hour and are the most common forgotten cost |
| **NAT gateways** | None left running; the reference estate's egress is torn down with it | A NAT gateway left up is the second most common forgotten cost |
| **Live deployment** | Reserved for the end-to-end demo — a handful of `apply` runs in A, torn down immediately | The only intentional spend |
| **Graph store** | Neo4j Community, not Neptune | See §5 |

Expected steady-state spend if disciplined: **under $20/month** (PMD §11, FD-05 §10). A weekly `terraform destroy` / resource-sweep check in C is the cheap insurance against a forgotten recorder.

---

## 7. Reference estate and harvest testing

Harvest and the live demo run against a **small, deliberately-flawed reference estate in Account A** (FD-05 §10), not against the generated corpus (which is never deployed). This estate is hand-built to contain, among clean resources, at least one **DF-7 relational defect** — the three-hop exfiltration path of FD-04 §12 — so the demo's "money shot" (PMD §9 step 4: the graph catches what Checkov misses) has a real target.

The reference estate is itself IaC (§8) so it can be stood up for a demo and torn down immediately after, keeping it out of steady-state cost.

---

## 8. Environment as code

The environment is reproducible infrastructure, part of deliverable 9 (PMD §8). A bootstrap Terraform module (`src/aws/`) provisions, per account:

- The cross-account roles and their trust policies + external IDs (§4).
- The S3 landing buckets and ETL wiring in C.
- The budget alarms (§6) — created by IaC so they cannot be forgotten.
- The reference estate in A (§7), as a separately-applied, separately-destroyed stack.

Account IDs and external IDs are supplied as variables, never hard-committed. This keeps the whole environment standable-from-scratch, which is both a reproducibility requirement and the cheapest way to guarantee the cost controls are always present.

---

## 9. Security posture of the environment

An enriched estate graph is a complete map of an institution's cloud attack surface (FD-03 §9); even in an academic build it warrants the protection production credentials get. The minimum posture:

- **Least privilege** on both cross-account roles — the harvest role's zero-write property (§4.1) is the load-bearing control.
- **External IDs** on every assume-role trust to prevent the confused-deputy problem.
- **Encryption at rest** on the Neo4j store and the S3 landing buckets; **access logging** on both.
- **No secrets in code or logs** — account IDs and external IDs are variables; the CLI host's credentials are short-lived assumed-role sessions, never long-lived keys.

Naming this candidly is better scholarship than omitting it (FD-03 §9): the framework's value and its risk share a source — a graph rich enough to reason about reachability is a graph rich enough to attack from.

---

## 10. Phase 0 exit criteria

Phase 0 is complete when, and only when:

1. Three accounts (or the documented single-account fallback) exist and are wired.
2. Budget alarms are live at $5/$15/$30 on every account — verified by a test breach alert, not just created.
3. A `hello world` cross-account read succeeds: C assumes `KGCRHarvestReadOnly` in A and reads a Config snapshot.
4. `KGCRProvisionApply` exists in A but is confirmed **unused** (write path wired, not yet exercised).
5. The bootstrap module (§8) stands the whole environment up and tears it down cleanly.

Only then does Phase 1 (FD-07 ontology encoding) begin.

---

## 11. Open items

| Ref | Item |
|---|---|
| — | Number of accounts actually granted — three (one per student, the expected case) uses §3 as written; if only one is available, the §4.2 single-account simulation applies. AWS Organizations is **not** a factor either way. |
| — | Region choice — single region (cheapest) vs a two-region pair to exercise cross-region resilience predicates (DF-5); single region is the lazy default, expand only if an archetype needs it |

---

## 12. References

1. AWS. *Organizations*, *IAM cross-account roles*, *STS AssumeRole with external ID* — trust-boundary primitives.
2. AWS. *Security Reference Architecture* and *Well-Architected — Security Pillar* — separation-of-duties reference.
3. AWS. *Budgets*, *Cost & Usage Reports*, *Config*, *CloudTrail* — cost governance and harvest sources.
4. HashiCorp. *Terraform* — environment-as-code and the corpus plan/apply model.
5. Neo4j. *Community Edition* — graph store (not Neptune, per FD-05 §10).
6. Institute of Internal Auditors. *The Three Lines Model* — the separation the read/write role split reproduces.
