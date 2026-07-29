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
| Amazon S3 | Evidence landing bucket for Config, CloudTrail and cost data; corpus and artefact storage | Planned |
| Amazon RDS | Represents the cardholder data store in the estates under analysis | Planned |
| AWS Lambda | ETL of harvested evidence into the graph schema; Advisor and Explainer inference | Planned |
| AWS Glue | Batch normalisation of large Config and Cost and Usage Report extracts | Planned |
| Amazon SageMaker | Train and host the recommender and the intent reconstructor | Planned — the reconstructor currently trains locally with scikit-learn |
| Amazon Bedrock | Structured intent extraction from a natural-language request, and verbalisation of an explanation. Never used to decide compliance | Planned |
| Amazon API Gateway | REST surface backing the `kgcr` CLI | Planned |
| Amazon Cognito | Authenticate architects, auditors and learners | Planned |
| AWS IAM | Cross-account roles enforcing separation of duties: Agent 2 read-only for harvesting, Agent 1 write-only for applying | **Terraform authored** in `src/aws/`, not yet applied |
| AWS Config | Resource inventory and relationships — the primary input to the estate graph | Planned |
| AWS CloudTrail | API audit events, supporting evidence-retention controls | Planned |
| AWS Cost and Usage Reports | Per-resource cost attribution for the joint cost/compliance objective | Planned |
| Amazon EventBridge | Scheduled and change-driven triggers for re-harvesting and drift detection | Planned |
| Amazon CloudWatch | Logs, metrics and alarms across all three accounts | Planned |
| AWS Budgets | Cost alarms, provisioned as code before any workload runs | **Terraform authored** in `src/aws/`, not yet applied |
| Amazon SNS | Deliver compliance findings and budget breach notifications | Planned |
| Amazon VPC, subnets, security groups, NAT, Internet Gateway | The network topology whose relationships the multi-hop defect analysis reasons over | Planned |
| AWS KMS | Encryption keys for the evidence bucket and the estates under analysis | Planned |
| Elastic Load Balancing | Ingress in the estates under analysis | Planned |
| AWS Organizations | Three-account structure: prod-payments, dev-staging, shared-security | Planned |

**Stated plainly:** what runs today is a local Python pipeline (`src/backend/`) plus authored but
unapplied Terraform (`src/aws/`). Phase-I asks for a service plan, and this is it; the gap between
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
| Ontology encoding (L1), recommender, Advisor, Explainer | Not started / blocked | See `CHANGELOG.md` §1 |

**Test suite:** 130 tests passing. Quality gates — `ruff check`, `ruff format --check`, `mypy`
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
- The compliance encoding (L1) is not yet written. Defect definitions cite control URIs that will
  resolve once the encoding is hand-authored, and by project rule that content is written by a human
  rather than generated.
- Intent reconstruction is a structural-feature baseline, not the graph neural network it is
  intended to become, and its calibration on the weakest axis is poor by design of the experiment
  rather than by accident.
