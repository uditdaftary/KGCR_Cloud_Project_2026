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
| Amazon S3 | Evidence landing bucket for Config, CloudTrail and cost data; corpus and artefact storage | Run-artifact bucket **Terraform authored** (`src/aws/run_artifacts.tf`), not applied; `kgcr review --s3-bucket` adapter tested against a mocked AWS (moto). A local directory is the default |
| Amazon RDS | Represents the cardholder data store in the estates under analysis | Planned |
| AWS Lambda | ETL of harvested evidence into the graph schema; Advisor and Explainer inference | Planned |
| AWS Glue | Batch normalisation of large Config and Cost and Usage Report extracts | Planned |
| Amazon SageMaker | Train and host the recommender and the intent reconstructor | Planned. Both currently train locally with scikit-learn |
| Amazon Bedrock | Structured intent extraction from a natural-language request, and verbalisation of an explanation. Never used to decide compliance | Planned. Gemini Flash (Google AI Studio, free tier) stands in for the advisor's proposals (one live run, 16 calls, see §9) and for free-text intent extraction (verified live; three responses recorded) |
| Amazon API Gateway | REST surface backing the `kgcr` CLI | Planned |
| Amazon Cognito | Authenticate architects, auditors and learners | Planned |
| AWS IAM | Cross-account roles enforcing separation of duties: Agent 2 read-only for harvesting, Agent 1 write-only for applying; a least-privilege publish policy for the pipeline | **Terraform authored and validated** (v1.16.5) in `src/aws/`, not applied |
| AWS Config | Resource inventory and relationships — the primary input to the estate graph | Planned. An adapter with an injected client (`kgcr.harvest.config`) reads five resource types and is tested against stubbed responses and moto; it has never read an account. The synthetic corpus stands in for harvest |
| AWS CloudTrail | API audit events, supporting evidence-retention controls | Planned |
| AWS Cost and Usage Reports | Per-resource cost attribution for the joint cost/compliance objective | Planned |
| Amazon EventBridge | Scheduled and change-driven triggers for re-harvesting and drift detection | Planned |
| Amazon CloudWatch | Logs, metrics and alarms across all three accounts | Planned |
| AWS Budgets | Cost alarms, provisioned as code before any workload runs | **Terraform authored and validated** in `src/aws/`, not applied |
| Amazon SNS | Deliver compliance findings and budget breach notifications | Contested-run topic **Terraform authored**, not applied; `kgcr review --sns-topic-arn` adapter tested against a mocked AWS (moto). Logged locally by default |
| Amazon VPC, subnets, security groups, NAT, Internet Gateway | The network topology whose relationships the multi-hop defect analysis reasons over | Planned |
| AWS KMS | Encryption keys for the evidence bucket and the estates under analysis | Planned |
| Elastic Load Balancing | Ingress in the estates under analysis | Planned |
| AWS Organizations | Three-account structure: prod-payments, dev-staging, shared-security | Planned |

**Stated plainly:** what runs today is a local Python pipeline (`src/backend/`, one command:
`kgcr review`) plus authored but unapplied Terraform (`src/aws/`). The pipeline reaches S3 and SNS through two
small interfaces. Local stand-ins are the default, and the AWS-backed adapters are tested against
moto's in-process mock. Nothing is deployed, the Terraform in `src/aws/` validates under Terraform
v1.16.5 but has not been applied, and no AWS spend has been incurred. Phase-I asks for a service plan, and this is it; the gap between
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
| Advisor (P6): rule floor, LLM admission filter, bounded loop, sycophancy protocol | Done; live run recorded, sycophancy gate PASS on 3 valid trials (1 invalid) | `src/backend/kgcr/advisor/`, 9 tests, `results/advisor_report.json` |
| Explainer (P9): exact paths, evaluated counterfactuals, three renderings | Done (templates, no LLM) | `src/backend/kgcr/explainer/`, 4 tests |
| End-to-end review command (P10) with local AWS stand-ins | Done, local | `src/backend/kgcr/orchestration/`, `kgcr review`, 8 tests (4 against a mocked AWS) |
| Design mode: a generated spec audited by the recommender, per-choice justifications, free-text intake | Done; free-text intake verified live | `src/backend/kgcr/design/`, `kgcr design`, `results/llm_fixtures/intent-v1-*.json` |
| Plan: immutable plans, diff, coverage, blast radius, monthly cost delta, Terraform backend | Done; Terraform validates and plans offline | `src/backend/kgcr/plan/`, `kgcr plan`, `plan/aws_prices.json` |
| Apply: local simulated, and a gated Terraform-backed path | Local done; **Terraform path never run** | `src/backend/kgcr/apply/`, `kgcr apply` |
| Authoring tools for the L1 controls and the gold register | Built; **no control signed off** | `src/backend/kgcr/gold/`, `dashboard/authoring.py` |
| Corpus D (TerraGoat, CloudGoat) against the rule floor | Done | `src/backend/kgcr/adversarial/`, `results/corpus_d_report.json` |
| Second labeller (Trivy) and inter-engine agreement | Done | `src/backend/kgcr/labelling/trivy_engine.py`, `results/labeller_agreement.json` |
| Automated explainer evaluation (FD-06 §9.1 and §9.2) | Done; the human study (§9.3) is not run | `src/backend/kgcr/explainer/evaluate.py`, `results/explainer_report.json` |
| AWS Config harvest adapter | Built; **never run against an account** | `src/backend/kgcr/harvest/config.py` |
| GNN against the forest | Done as an ablation | `src/ml_model/gnn_ablation.py`, `results/gnn_ablation.json` |

**Test suite:** 474 tests passing on the build machine (Python 3.14, with Checkov, Trivy and Terraform installed); a clean Python 3.12 venv with only the dev extra passes 457 and skips 4; CI itself has not run on these commits. Quality gates — `ruff check`, `ruff format --check`, `mypy`
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
   quality. That is why a random forest was used rather than a GNN; a later ablation (result 10)
   found a small exact-set gain for a graph network, which an edge-free control reproduces.
   The CRITICAL mask removes the one illegal option in the pool even when it is forced to
   rank first.
4. **Advisor, rule floor (objective O2).**
   - DF-1 to DF-4 recall is 1.000. This holds by construction, because the injectors produce
     exactly what the rules check, so it is a sanity floor rather than a benchmark.
   - DF-5, DF-6 and DF-7 recall is 0.000. Those findings need the LLM path.
   - Clean estates raise no CRITICAL finding.
   - **Live LLM run** (16 Gemini calls, `gemini-3.7-flash`, recorded in `results/llm_fixtures/`):
     the sycophancy gate is **PASS** on 3 valid trials, with every model finding persisting through
     three pressure passes. The fourth trial (`privilege_escalation_passrole`) is invalid, because
     the model raised nothing on pass 1. Recall beyond the rule floor is 2 of 4 variants
     (`transitive_trust_chain` and `no_database_backup` found; `indirect_internet_reachability` and
     `privilege_escalation_passrole` missed). It raised 1 CRITICAL finding on 4 clean estates, a
     false positive. All 6 proposals were grounded and admitted. This is one run with one seed on
     synthetic estates and 4 trials, so it shows the protocol works, not a general rate.
5. **Explanation (objective O5).** For every defect variant, the architect, auditor and learner
   renderings yield identical claim sets (INV-2): controls, severities, resources and counterfactual
   outcomes, extracted back out of the rendered text.

6. **Independent configurations (Corpus D).** CloudGoat (740 AWS resources) and TerraGoat (63),
   both deliberately vulnerable and written by others, parsed and never executed. The rule floor's
   seven rules cover 31 of the 787 checks Checkov fails in CloudGoat and 5 of 215 in TerraGoat, so
   they describe a small slice of what is wrong in real configurations. Where it can read the
   values it agrees with Checkov: database encryption (all 4 that Checkov fails in CloudGoat, 1 of 1 in TerraGoat),
   CloudTrail validation (2 of 2). It misses where an argument is an unresolved expression: 16 of
   the 36 CloudGoat security groups and 2 IAM policies. There are no per-resource labels, so this
   is agreement and coverage, not accuracy.
7. **Second labeller (Trivy).** On 6 seeded estates per family (24 seeded defects and their 24 clean parents), with Checkov reading Terraform plan JSON and Trivy 0.75.0 reading `.tf.json`: the rule floor recalls all 24 by construction. Checkov recalls DF-2, DF-3 and DF-4 (18 of 18) and none of DF-1; Trivy recalls DF-2 and DF-4 and neither DF-1 nor DF-3. No engine flagged a clean parent. DF-1 is the injector's world-open port 443, which neither tool treats as a defect, so that disagreement is about the definition, not an engine error. Cohen's kappa between Checkov and Trivy is 1.0 on DF-2 and DF-4, 0.0 on DF-3 and undefined on DF-1 (neither flags anything). Checkov reading `.tf.json` recalled 0 of 24, which is why plan JSON is the input. With 6 estates a family these are indications, not rates.
8. **Explainer evaluation (objective O5, FD-06 §9.1 and §9.2).** Over 12 stored bundles (the nine
   seeded variants and three designed estates): cross-audience invariance holds for 12 of 12;
   counterfactual validity, checked against the outcome the advisor loop observed after applying
   the repair rather than recomputed, is 4 of 4; sparsity is a mean of 0.078 of the estate's
   resources (n = 7 findings); Fidelity+ and Fidelity- hold for the one relational finding. The
   samples are small because recorded model responses exist for only five of the nine variants, so most
   bundles carry rule-floor findings only. The human study (§9.3) is not run.
9. **Cost delta.** A plan prices the resources it creates from AWS list prices (45 items, three
   regions, retrieved 2026-10-13), at 730 hours a month, and lists what it cannot price (data
   transfer, requests, S3 volume) instead of counting it as zero. A Haiku subagent collected the
   prices from the official price files; the main thread then re-derived every EC2, RDS, load
   balancer, KMS and S3 value from freshly downloaded files and CloudTrail and Glue by SKU, and all
   matched. It is a list-price estimate, not a bill.
10. **Graph network against the forest.** The expectation, recorded before running, was no gain.
    On 99 test estates across four corpus seeds the forest recovers the exact option set for 0.941
    of estates and a two-layer network over the resource-type graph for 0.991; the same network with
    its edges removed scores 0.984. R-precision and NDCG are at or near 1.0 for every model (the lowest is 0.9945). So a neural
    ranker is a little better at exact-set recovery here, but the graph structure is not shown to
    be the reason.

---

## 10. Contribution matrix (as built)

Records who authored what in this repository today. Cells for Manya and Tanmoy stay empty until
their branches contain the work; nothing is credited on their behalf.

| Activity | Udit | Manya | Tanmoy |
|---|---|---|---|
| Literature survey (5 papers each) | ✓ (papers 1-5) | papers 6-10 | papers 11-15 |
| Research gap analysis (5 papers each) | ✓ | theirs | theirs |
| Cloud environment, IAM, Terraform | ✓ | | |
| Backend development and CLI | ✓ | | |
| Knowledge graph, ontology, corpus | ✓ | | |
| AI / machine learning (reconstruction, recommender, advisor) | ✓ | | |
| Explainability and evaluation | ✓ | | |
| Dashboard (Phase-I visual summary) | ✓ | | |
| AWS cloud services (adapters, planning table) | ✓ | | |
| Testing and CI | ✓ | | |
| Documentation, presentation | ✓ | | |

The AI/ML and explainer code was written by Udit with Claude as a coding assistant.

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

- The corpus is synthetic. No real financial-sector estate is used. Corpus D (TerraGoat, CloudGoat)
  shows the rule floor covers 2 to 4% of what Checkov fails in independently written
  configurations; it has no per-resource labels, so it measures agreement, not accuracy.
- The AWS deployment is planned, not built. The Terraform for budget alarms and cross-account IAM
  validates under Terraform v1.16.5 but has not been applied to live accounts. The Terraform-backed
  apply and the AWS Config harvest adapter have never touched an account: they are tested against
  fakes. A valid offline plan does not mean an apply would succeed, and the shipped write role
  (`ec2`, `s3`) would refuse every generated estate at the permission preflight.
- The compliance encoding (L1) exists only as a six-control draft slice written by Claude. By project
  rule L1 is human-authored, so it counts only after Udit reviews each entry; the clause numbers were
  checked against secondary sources, not the standards themselves.
- The advisor's live run is one pass over 4 trials: the gate passed on 3 valid ones, the model
  missed 2 of 4 relational or resilience variants, and it raised one false CRITICAL on a clean
  estate. The L1 controls the model cites are unverified drafts.
- The recommender is a random forest over intent. A graph network scored slightly higher on
  exact-set recovery in an ablation, and not because of the graph. The cost delta is an on-demand
  list-price estimate at 730 hours a month; it excludes data transfer, requests and storage volume
  and has not been compared with a bill.
- Free-text intake was verified live and three responses are recorded. Gemini responses for seven
  of the nine review variants are not recorded, because the free-tier daily quota was spent.
- The human study is not run: it needs ethics approval and participants. The L1 authoring tools
  are built and no control has been signed off.
- Intent reconstruction is a structural-feature baseline, not the graph neural network it is
  intended to become, and its calibration on the weakest axis is poor by design of the experiment
  rather than by accident.
