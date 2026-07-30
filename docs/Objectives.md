# Project Objectives

**Project:** KGCR — Knowledge Graph-Based Cloud Configuration Recommendation
**Course:** BCSE355L Cloud Architecture Design Project, Phase-I

Six objectives. Each states what will be built and how it will be measured, so that at the end of
the project each one can be marked met or not met against evidence rather than opinion.

---

**O1 — Encode cloud compliance controls as a queryable knowledge graph.**
Represent PCI-DSS v4.0 and the CIS AWS Foundations Benchmark as a graph layer (L1) in which each
control is linked to the concrete AWS resource properties that satisfy it, across three workload
archetypes: a payments API, a customer data platform, and an internal reporting service.
*Measure:* number of controls encoded and hand-verified against the published standard; a gold set
of 50–100 reference configurations that the encoding classifies correctly.

**O2 — Detect multi-hop misconfigurations that single-resource policy engines cannot reach.**
Build a dependency graph of an AWS estate and detect relational defects — a resource reachable from
the internet through a chain of individually compliant resources, a transitive trust chain, a
privilege-escalation path through `iam:PassRole` — where every resource in the chain passes a
per-resource scan.
*Measure:* on the relational defect set, the proportion of defects the graph recovers versus the
proportion an established policy engine (Checkov, including its graph checks) reports.
*Status:* **met for the current defect set** — the graph recovers 12 of 12 relational defects while
Checkov's verdict on the sensitive sink is byte-identical to the clean parent estate in all 12
cases.

**O3 — Recommend a compliant, cost-aware AWS configuration from a workload described in business
terms.** Take a statement such as "a payments API handling cardholder data in eu-west-2", produce a
concrete Terraform specification, and rank candidates jointly on compliance coverage and monthly
cost rather than optimising one at the expense of the other.
*Measure:* proportion of generated specifications that pass the encoded controls without manual
correction; cost delta against a compliance-only baseline on the same intent.

**O4 — Reconstruct the design intent of an existing estate and report calibrated confidence per
field.** Recover the intent an already-deployed estate was built to serve — archetype, network
layout, logging posture, availability spread, IAM shape — from its structure alone, and report a
confidence for each field so that low-confidence fields are escalated for user confirmation rather
than silently assumed.
*Measure:* per-field accuracy and per-field expected calibration error (ECE) on an estate-level
held-out split, reported per field and never pooled.
*Status:* **baseline met** — structurally encoded axes reconstruct at 1.000 accuracy with
ECE ≤ 0.052; `iam_shape`, which the estate carries no structural trace of, reconstructs at 0.417
with ECE 0.282, and that miscalibration is surfaced rather than hidden.

**O5 — Produce audit-grade explanations as extracted reasoning paths, not narrated prose.**
For every recommendation or finding, return the subgraph that links the configuration choice to the
regulatory clause and the cost or risk consequence, together with a counterfactual stating the
minimal change that would alter the verdict.
*Measure:* proportion of explanations that are exact reasoning paths rather than approximations;
invariance test showing that the architect, auditor and learner renderings differ in form but never
in conclusion.

**O6 — Deploy the system on a governed multi-account AWS environment with cost controls active from
day one.** Operate across three accounts with a read-only harvesting role and a separate write role,
Amazon CloudWatch monitoring, Amazon SNS notifications, and AWS Budgets alarms provisioned as
Infrastructure as Code before any workload runs.
*Measure:* Terraform for the budget alarms and the cross-account role split applies cleanly; a
cross-account read completes; no month exceeds the configured budget without an alarm firing.
*Status:* Terraform authored in `src/aws/`, not yet applied.
