# Project Report — Phase I

**Project title:** KGCR — Knowledge Graph-Based Cloud Configuration Recommendation
**Repository:** `KGCR_Cloud_Project_2026`
**Course:** BCSE355L — Cloud Architecture Design Project
**Course instructor:** Dr. Priya V
**Team:** Udit (lead), Manya, Tanmoy
**Cloud platform:** Amazon Web Services

---

## 1. Abstract

Cloud misconfiguration remains a leading cause of data breaches, and the tools meant to prevent it
each cover one edge of the problem. Posture management products detect violations only after
deployment. Policy-as-code engines such as Checkov evaluate one resource at a time, justify a
finding only by restating the rule that fired, and cannot see a defect that lives in the
relationship between two individually compliant resources. FinOps platforms find waste but are blind
to compliance. Nothing recommends a configuration at design time, grounds it in a regulatory clause,
optimises cost and compliance together, and explains itself well enough to survive an audit.

This project builds that missing middle. Controls from PCI-DSS v4.0 and the CIS AWS Foundations
Benchmark, the resources and dependencies of an AWS estate, and the history of past runs are encoded
in one knowledge graph, so recommendation, review, cost reasoning and explanation become operations
over a single structure. Because the estate is a graph, a defect can be a path rather than a
property: a cardholder data store reachable from the internet through a chain in which every
resource passes its own check. Review is reframed as design with recovered intent — the system
reconstructs what an estate was built to achieve, reports calibrated confidence per field, and
reviews against that reconstruction rather than a fixed checklist. Each conclusion is explained as
the reasoning subgraph linking a configuration choice to its controlling clause and its cost
consequence.

The planned AWS deployment spans three accounts. AWS Config, CloudTrail and Cost and Usage Reports
feed Amazon S3; Lambda and Glue normalise that evidence into Neo4j on EC2; SageMaker trains the
models; API Gateway and Cognito expose and authenticate the interface; IAM separates harvesting from
writing; CloudWatch, Budgets and SNS provide monitoring, cost control and notification.

*(296 words)*

---

## 2. Literature survey

Fifteen papers, all published 2023–2026 in IEEE, Springer, Elsevier, ACM or MDPI venues, with the
full table of Method / Dataset / Advantages / Limitations / Research Gap.

See [Literature_Survey.md](Literature_Survey.md).

## 3. Research gap analysis

Per student, five papers each, written independently.

- Udit — papers 1–5: [Research_Gap_Udit.md](Research_Gap_Udit.md)
- Manya — papers 6–10: `Research_Gap_Manya.md` (to be written by Manya)
- Tanmoy — papers 11–15: `Research_Gap_Tanmoy.md` (to be written by Tanmoy)

## 4. Objectives

Six measurable objectives — see [Objectives.md](Objectives.md).

## 5. Novelty summary

See [Novelty.md](Novelty.md).

## 6. Proposed architecture

| Diagram | File |
|---|---|
| 1 — AWS Cloud Architecture | [`architecture/AWS_Architecture.png`](../architecture/AWS_Architecture.png) |
| 2 — Complete System Architecture | [`architecture/System_Architecture.png`](../architecture/System_Architecture.png) |

Two supporting flowcharts expand the decision logic of the two entry conditions; see
[`architecture/README.md`](../architecture/README.md).

## 7. Dataset details

See [`dataset/dataset_description.md`](../dataset/dataset_description.md). In summary: the corpus is
generated, not downloaded — 180 synthetic AWS estates carrying 2,331 resources, each with its
originating intent as ground truth, plus a 12-estate relational defect set.

---

## 8. AWS services planning

Every service planned for the implementation, with its purpose. This is a **planning** table, which
is what Phase-I asks for; the final column states honestly what is running today.

| AWS service | Purpose in this project | Status |
|---|---|---|
| Amazon EC2 | Host Neo4j Community (the knowledge graph store) and the analysis workload | Planned |
| Amazon S3 | Evidence landing bucket for Config, CloudTrail and cost data; corpus and artefact storage | Planned. A local directory stands in for the run-artifact bucket today |
| Amazon RDS | Represents the cardholder data store in the estates under analysis | Planned |
| AWS Lambda | ETL of harvested evidence into the graph schema; Advisor and Explainer inference | Planned |
| AWS Glue | Batch normalisation of large Config and Cost and Usage Report extracts | Planned |
| Amazon SageMaker | Train and host the recommender and the intent reconstructor | Planned. Both currently train locally with scikit-learn |
| Amazon Bedrock | Structured intent extraction from a natural-language request, and verbalisation of an explanation. Never used to decide compliance | Planned. Gemini Flash (Google AI Studio, free tier) stands in for the advisor's proposals; its live run is pending |
| Amazon API Gateway | REST surface backing the `kgcr` CLI | Planned |
| Amazon Cognito | Authenticate architects, auditors and learners | Planned |
| AWS IAM | Cross-account roles enforcing separation of duties: Agent 2 read-only for harvesting, Agent 1 write-only for applying | **Terraform authored** in `src/aws/`, not yet applied |
| AWS Config | Resource inventory and relationships — the primary input to the estate graph | Planned. The synthetic corpus stands in for harvest |
| AWS CloudTrail | API audit events, supporting evidence-retention controls | Planned |
| AWS Cost and Usage Reports | Per-resource cost attribution for the joint cost/compliance objective | Planned |
| Amazon EventBridge | Scheduled and change-driven triggers for re-harvesting and drift detection | Planned |
| Amazon CloudWatch | Logs, metrics and alarms across all three accounts | Planned |
| AWS Budgets | Cost alarms, provisioned as code before any workload runs | **Terraform authored** in `src/aws/`, not yet applied |
| Amazon SNS | Deliver compliance findings and budget breach notifications | Planned. Contested runs are logged locally in its place |
| Amazon VPC, subnets, security groups, NAT, Internet Gateway | The network topology whose relationships the multi-hop defect analysis reasons over | Planned |
| AWS KMS | Encryption keys for the evidence bucket and the estates under analysis | Planned |
| Elastic Load Balancing | Ingress in the estates under analysis | Planned |
| AWS Organizations | Three-account structure: prod-payments, dev-staging, shared-security | Planned |

**Stated plainly:** what runs today is a local Python pipeline (`src/backend/`, one command:
`kgcr review`) plus authored but unapplied Terraform (`src/aws/`). Where the pipeline will touch S3
and SNS it goes through two small interfaces with local stand-ins behind them; nothing is deployed and
no AWS spend has been incurred. Phase-I asks for a service plan, and this is it; the gap between
plan and implementation is stated rather than concealed, and Diagram 1 carries the same note.

---

## 9. Implementation progress

| Component | Status | Evidence |
|---|---|---|
| Reproducibility spine — deterministic seeding, canonical hashing, run records | Done | `src/backend/kgcr/`, 30 tests |
| Intent-first corpus generator and dependency graph | Done | `src/backend/kgcr/corpus/`, 45 tests |
| Defect taxonomy DF-1…DF-7 and the relational (DF-7) test set | Done | `src/backend/kgcr/defects/`, 34 tests |
| Checkov labelling and the empirical relational-defect gate | Partial | `src/backend/kgcr/labelling/`, 8 tests, `results/p4_df7_checkov_evidence.json` |
| Intent reconstruction with per-field calibration | Done (structural baseline) | `src/backend/kgcr/reconstruction/`, 13 tests, `results/reconstruction_report.json` |
| Cross-account IAM and budget alarms as Terraform | Authored, not applied | `src/aws/` |
| L1 control slice (6 controls) | Draft, awaiting Udit's review | `src/backend/kgcr/advisor/controls_DRAFT-FOR-UDIT-REVIEW.json` |
| Recommender (P7): retrieve, rank, CRITICAL mask | Done (random forest, not a GNN) | `src/backend/kgcr/recommender/`, 5 tests, `results/recommender_report.json` |
| Advisor (P6): rule floor, LLM admission filter, bounded loop, sycophancy protocol | Code done; live LLM run and sycophancy gate not run | `src/backend/kgcr/advisor/`, 9 tests, `results/advisor_report.json` |
| Explainer (P9): exact paths, evaluated counterfactuals, three renderings | Done (templates, no LLM) | `src/backend/kgcr/explainer/`, 4 tests |
| End-to-end review command (P10) with local AWS stand-ins | Done, local | `src/backend/kgcr/orchestration/`, `kgcr review`, 4 tests |

**Test suite:** 151 tests passing. Quality gates — `ruff check`, `ruff format --check`, `mypy`
(strict) and `pytest` — run in CI on Python 3.11 and 3.12 on every push.

### Results obtained so far

1. **Multi-hop detection (objective O2).** Across 12 relational-defect estates, the graph recovers
   all 12 paths while Checkov, including its graph checks, returns a verdict on the sensitive sink
   that is byte-identical to the clean parent estate in all 12 cases. This is the empirical form of
   the project's central claim.
2. **Intent reconstruction and calibration (objective O4).** On the 180-estate corpus with an
   estate-level split, structurally encoded axes reconstruct at 1.000 accuracy with expected
   calibration error at or below 0.052. `iam_shape`, which the estate carries no structural trace
   of, reconstructs at 0.417 accuracy with ECE 0.282 — confidently wrong. Reporting that
   miscalibration rather than hiding it is why confidence is reported per field and never pooled.
3. **Recommendation (objective O3).** On the same held-out split (24 estates), the recommender
   recovers the exact option set for 0.958 of estates from true intent and 0.958 from
   P8-reconstructed intent. Baselines: per-archetype frequency 0.208, global popularity 0.000.
   R-precision is 1.000, against 0.940 and 0.858 for the baselines. The generator is a function of
   intent, so this measures recovery of the generator's mapping, not real-world recommendation
   quality. That is also why a random forest was used rather than a GNN: a GNN had no headroom to
   show. The CRITICAL mask removes the one illegal option in the pool even when it is forced to
   rank first.
4. **Advisor, rule floor (objective O2).**
   - DF-1 to DF-4 recall is 1.000. This holds by construction, because the injectors produce
     exactly what the rules check, so it is a sanity floor rather than a benchmark.
   - DF-5, DF-6 and DF-7 recall is 0.000. Those findings need the LLM path.
   - Clean estates raise no CRITICAL finding.
   - The sycophancy-resistance gate has **not run**. It needs live Gemini calls, and no result is
     claimed for it.
5. **Explanation (objective O5).** For every defect variant, the architect, auditor and learner
   renderings yield identical claim sets (INV-2): controls, severities, resources and counterfactual
   outcomes, extracted back out of the rendered text.

---

## 10. Expected contribution matrix

| Activity | Udit | Manya | Tanmoy |
|---|---|---|---|
| Literature survey (5 papers each) | ✓ | ✓ | ✓ |
| Research gap analysis (5 papers each) | ✓ | ✓ | ✓ |
| Cloud environment, IAM, multi-account setup | ✓ | | |
| Backend development and CLI | ✓ | | |
| Knowledge graph, ontology, corpus | | ✓ | |
| Database and graph store integration | | ✓ | |
| AI / machine learning | | | ✓ |
| Explainability and evaluation | | | ✓ |
| Frontend development | | | ✓ |
| AWS cloud services | ✓ | ✓ | ✓ |
| Testing | ✓ | ✓ | ✓ |
| Documentation | ✓ | ✓ | ✓ |
| Presentation | ✓ | ✓ | ✓ |
| GitHub commits | ✓ | ✓ | ✓ |

---

## 11. Repository

**URL:** https://github.com/uditdaftary/KGCR_Cloud_Project_2026

Branch model: `main` ← `develop` ← `feature/udit` | `feature/manya` | `feature/tanmoy`. Each member
works only on their own feature branch and merges into `develop` by pull request after review.

```
KGCR_Cloud_Project_2026/
├── README.md, LICENSE, .gitignore
├── docs/            Project_Report, Literature_Survey, Research_Gap, Objectives, Novelty, FD-01…FD-08, PMD
├── architecture/    AWS_Architecture.png, System_Architecture.png, condition flowcharts
├── dataset/         raw/, processed/, dataset_description
├── src/             frontend/, backend/, ml_model/, aws/
├── results/         relational-defect evidence, reconstruction report
└── presentation/
```

---

## 12. Limitations stated up front

- The corpus is synthetic. No real financial-sector estate is used, and results have not yet been
  checked against human-authored insecure configurations (Corpus D is planned, not present).
- The AWS deployment is planned, not built. The Terraform for budget alarms and cross-account IAM is
  authored but has not been applied to live accounts.
- The compliance encoding (L1) exists only as a six-control draft slice written by Claude. By project
  rule L1 is human-authored, so it counts only after Udit reviews each entry; the clause numbers were
  checked against secondary sources, not the standards themselves.
- The advisor's LLM path has not run live, so relational (DF-7) and resilience (DF-5) findings are
  not yet produced by the demo, and the sycophancy gate is open.
- The recommender is a random forest over intent, not a graph neural network, and no cost model
  exists yet, so objective O3's cost delta is unmeasured.
- Intent reconstruction is a structural-feature baseline, not the graph neural network it is
  intended to become, and its calibration on the weakest axis is poor by design of the experiment
  rather than by accident.
