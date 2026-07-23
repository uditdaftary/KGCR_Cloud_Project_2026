# PMD — Project Master Document

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Working codename:** KGCR *(provisional)*
**Document ID:** PMD — keystone document
**Status:** Baseline
**Binds:** FD-01 through FD-06

---

## 1. Thesis

> Given a workload specification stated in business terms, recommend a concrete AWS configuration and justify that recommendation as a traceable subgraph linking each choice to a regulatory clause and a cost or risk consequence — and perform the same operation in reverse on an existing estate, by first reconstructing the intent it was built to serve.

**One-line pitch.** An experienced cloud architect who has read every compliance standard, never forgets one, and writes down their reasoning every single time.

---

## 2. Problem

Financial institutions face three pressures simultaneously, and no existing tool addresses them jointly.

**Misconfiguration, not exploitation, is the dominant breach vector.** The canonical case is Capital One (2019): approximately 100 million records exposed through a misconfigured web application firewall and an over-permissive IAM role. No zero-day. Every individual component was functioning as configured.

**Compliance obligations are relational and must be evidenced.** PCI-DSS, DORA, and sector regulators require not only that controls are met but that the institution can demonstrate *why* a given configuration meets them, months or years after the fact. In practice this justification is reconstructed retrospectively from meeting notes and institutional memory.

**Cost sprawl is unmanaged against compliance.** Cost optimisation and compliance hardening are handled by different teams using different tools, and their recommendations routinely conflict.

**The market gap.** CSPM tools (Wiz, Prisma Cloud, Orca) detect violations in what exists. FinOps tools (CloudHealth, Cloudability) find waste. Neither *recommends a configuration* that jointly satisfies compliance, cost, and resilience with an audit-grade justification. And no tool answers the design-time question at all: *what should I build?*

---

## 3. Contributions

Five claims, ordered by strength. Each maps to a specific evaluation.

| # | Contribution | Evidence | Document |
|---|---|---|---|
| **C1** | **Relational defect detection.** A graph representation identifies multi-hop compliance violations that single-resource policy engines cannot reach by construction. | Comparative recall on the DF-7 test set against Checkov / tfsec / Prowler, which score zero by construction | FD-05 §5, FD-04 §12 |
| **C2** | **Intent reconstruction.** Configuration review reframed as design with recovered intent, enabling context-sensitive review rather than checklist matching. | Round-trip fidelity on intent-first synthetic corpus | FD-01 §7, FD-05 §8 |
| **C3** | **Explanation as reasoning path, not narration.** Because compliance logic is curated rather than learned, explanations are exact for the majority of elements rather than approximate. | Fidelity / sparsity metrics; symbolic path coverage rate | FD-06 §5 |
| **C4** | **Audience-relative explanation with invariant content.** Explanation sufficiency is audience-relative; adequacy is not. | Cross-audience invariance test; human study on comprehension and appropriate reliance | FD-06 §8–9 |
| **C5** | **Bounded adversarial review with graceful non-convergence.** A compliance gate that reports irresolvable disagreement rather than manufacturing agreement. | Passes-to-convergence distribution; cap ablation; sycophancy-resistance test | FD-02, FD-04 §10 |

C1 and C3 are the strongest. Lead with them.

---

## 4. Document map

| ID | Title | Covers |
|---|---|---|
| **PMD** | Project Master Document | This document — thesis, scope, plan, risk, commercial |
| **FD-01** | Unified Flow Specification | Pipeline, stages, terminal states, invariants, CLI |
| **FD-02** | Advisor Iteration Policy | Loop bounds, severity taxonomy, contested findings |
| **FD-03** | Feedback Loop Specification | Run records, L1/L2/L3 layering, learning uses, pathologies |
| **FD-04** | Advisor Persona Specification | Reviewer role, grounding rule, calibration, evaluation |
| **FD-05** | Data Strategy and Corpus Construction | Corpus sources, defect taxonomy, weak supervision, circularity defences |
| **FD-06** | Explainer Specification | Subgraph extraction, counterfactuals, audience modes, XAI evaluation |
| **FD-07** | Ontology Specification | L1 node/edge schema, control-to-config crosswalk, severity derivation, FIBO/OSCAL integration |
| **FD-08** | Environment Build | Three-account topology, cross-account IAM, cost controls, Phase 0 exit |

---

## 5. Decision register

| ID | Decision | Status | Resolution |
|---|---|---|---|
| D1 | Who is the user? | **Resolved** | All personas; one pipeline, three explanation renderings (FD-06 §8) |
| D2 | Scope breadth | **Resolved** | 3 archetypes, 2 enforced frameworks (FD-05 §3) — accepted |
| D3 | Training data provenance | **Resolved** | Four-source corpus, weak supervision (FD-05) |
| D4 | Product form | **Resolved** | CLI |
| D5 | Deployment artifact format | **Resolved** | Terraform — accepted; plan/apply already assumed by INV-3 (FD-08 §5) |
| D6 | Explanation export format | **Resolved** | OSCAL assessment-results — accepted (FD-06 §10) |
| D7 | Three-account topology mapping | **Resolved** | Standalone accounts + cross-account roles, **no AWS Organizations dependency** (FD-08 §3) — accepted |
| D8 | Advisor base model | **Resolved** | Different model from Recommender — accepted (FD-04 §11) |
| D9 | Path expansion hop bound *k* | **Resolved** | Default *k* = 3 — accepted; ablation reports the trade-off (FD-04 §7) |
| D10 | ADVISORY finding rate limit | **Resolved** | Capped at 5/run, ranked by control-node specificity; overflow logged (FD-04 §6) — accepted |
| D11 | Cost data source | **Resolved** | Static price snapshot — accepted; reproducibility over currency |
| D12 | OSCAL internal vs export-only | **Resolved** | Export-only; OSCAL for import/export, native graph internal (FD-07 §9). Absorbs D16. |
| D13 | Gold-set expert review protocol | **Resolved** | Instructor (+ any external practitioner) reviews the crosswalk; spreadsheet instrument (FD-05 §11) — accepted |
| D14 | Sparsity operating point per audience | **Resolved** | Curve then read off: auditor = max evidence, architect = knee, learner = knee + expansion (FD-06 §5) — accepted |
| D15 | `learner` mode in human study | **Resolved** | Held as a demonstration feature, not a study arm; new-data ingestion kept low-friction via the FD-03 enrichment loop — accepted |
| D16 | *(merged into D12)* | **Resolved** | See D12 / FD-07 §9 |
| D17 | Human study recruitment | **Resolved** | Available pool is 3 students + 1 instructor (n ≈ 4); run as a **pilot**, external practitioners as upside (FD-06 §9.3) |

**Critical path:** D2 → corpus generation → everything downstream. **D2 is now confirmed; corpus generation is unblocked.** All register decisions are resolved.

---

## 6. Architecture summary

**Three-account estate** (AWS Organizations pattern):

| Account | Role | Contents |
|---|---|---|
| **A — prod-payments** | Estate under analysis | Reference deployment; harvest target |
| **B — dev-staging** | Drift comparison | Divergent copy of A |
| **C — shared-security** | Analysis platform | Graph store, models, CLI host, cross-account read roles |

**Stack:** AWS Config + CloudTrail + Cost & Usage Reports → S3 → Lambda/Glue ETL → **Neo4j Community** (not Neptune — it bills continuously). Recommender and Advisor as separate models. Bedrock or API-hosted LLM for extraction and verbalisation only.

**Ontology layers:** AWS Config resource schema (topology) + NIST OSCAL (control encoding) + FIBO (financial domain). Citing FIBO buys real academic legitimacy for the domain layer at low cost.

---

## 7. Course coverage

The project must demonstrate depth in two courses. This section is the checklist for that.

### Cloud Architecture and Design

| Concept | Where it appears |
|---|---|
| Multi-account landing zone, AWS Organizations | Three-account topology (§6) |
| IAM, cross-account roles, least privilege, separation of duties | INV-5 (Agent 2 read-only, Agent 1 write-only) |
| VPC, subnet, security group, routing design | Dependency graph (FD-01 S4); relational findings (DF-7) |
| High availability, multi-AZ, fault domains | Resilience defect class DF-5; availability targets in WorkloadIntent |
| Infrastructure as Code, declarative provisioning | Terraform corpus generation; Agent 1 artifact |
| Plan/apply, change control, blast radius | INV-3, stages S9–S10 |
| Well-Architected pillars | Gold set source; joint optimisation objective |
| Cloud security posture management, drift detection | Review mode; post-apply drift (FD-03 C4) |
| FinOps, cost optimisation, right-sizing | Cost defect class DF-6; counterfactual cost deltas |
| Shared responsibility model, defence in depth | Framing of control coverage |
| Observability, audit logging, evidence retention | Defect class DF-4; FD-03 §9 |
| Compliance frameworks in cloud context | L1 encoding; PCI-DSS / CIS |

### Artificial Intelligence

| Concept | Where it appears |
|---|---|
| Knowledge representation, ontologies, semantic modelling | L1 layer; FIBO/OSCAL integration |
| Graph data structures, traversal, reachability | Path expansion (FD-04 §7); relational findings |
| Graph neural networks (R-GCN / GraphSAGE) | Recommender; heterogeneous graph learning |
| Link prediction, recommender systems, learning-to-rank | S2 ranking; preference pairs (FD-03 §6) |
| Constraint satisfaction and masking | Constraint mask (FD-01 S2) |
| Weak supervision, programmatic labelling | FD-05 §6 |
| Classification with confidence calibration | Intent reconstruction (FD-05 §8) |
| Explainable AI — subgraph, counterfactual, attribution | FD-06 §5–6; SHAP as comparison baseline |
| Faithfulness vs plausibility in explanation | FD-06 §9.1 |
| LLM structured extraction and constrained generation | S1a intent capture; FD-06 §7 verbalisation |
| Multi-agent systems, role separation, adversarial review | Advisor/Recommender/Explainer separation; INV-7 |
| Human-in-the-loop, preference learning, appropriate reliance | S8 gate; FD-03 §6; FD-06 §9.3 |
| Evaluation design, ablation, leakage control | FD-05 §9; cap ablation (FD-02 §8) |

Both lists are dense enough that the risk is not insufficient coverage but insufficient depth. See §11.

---

## 8. Deliverables

1. **CLI implementation** — `design`, `review`, `explain`, `plan`, `apply`, `history`
2. **Knowledge graph** — L1 encoded for PCI-DSS v4.0 and CIS AWS Foundations; L2/L3 schemas implemented
3. **Corpus** — 2,000–5,000 synthetic estates, ~500 mined, 50–100 gold, adversarial imports
4. **Trained components** — recommender, intent reconstructor
5. **Evaluation suite** — automated metrics, comparative tables against policy engines, ablations
6. **Human study** — protocol, results, analysis
7. **Working demonstration** — the five-minute end-to-end run (§9)
8. **Dissertation / report** — with these foundation documents as appendices
9. **Reproducibility package** — corpus generator, pinned model and graph versions, seeds

---

## 9. The demonstration

The five-minute run that everything else serves. Rehearse this early; it exposes integration gaps faster than any test suite.

1. `kgcr design --intent "payments API, cardholder data, 5k TPS, PCI-DSS, multi-AZ"` → recommendation appears with cost estimate
2. `--audience=auditor` on the same run → same conclusions, control-first rendering (INV-2 made visible)
3. `kgcr review --account A` on a deliberately flawed estate → surfaces a **relational** finding no scanner catches (C1, live)
4. Show the same estate through Checkov → it finds the individual issues and misses the path
5. Counterfactual: remove the offending permission → cost and compliance delta recomputed
6. `kgcr plan` → diff shown; **do not apply** during the demo
7. `kgcr explain --run <earlier-id>` → identical bundle re-emitted from storage (audit trail integrity)

Step 4 is the money shot. It shows the graph doing something a production tool cannot.

---

## 10. Milestone plan

Phase-based rather than date-based; anchor to your actual term calendar. Sequence is dependency-ordered and should not be parallelised past a broken step.

| Phase | Work | Exit criterion |
|---|---|---|
| **0 — Foundation** | Confirm D2; environment build; budget alarms; repo and reproducibility scaffolding | Three accounts wired, alarms live, `hello world` cross-account read works |
| **1 — Ontology** | Encode L1: PCI-DSS + CIS controls mapped to AWS service properties | Controls queryable; severity derivable from graph |
| **2 — Gold set** | Hand-build and label 50–100 reference configurations | Gold set frozen; validates L1 encoding |
| **3 — Generator** | Intent-first Terraform generator; corpus A without defects | 500 estates generated, parsed into graph |
| **4 — Labelling** | Checkov/tfsec/Prowler pipeline; weak-supervision label model | Labels produced with agreement statistics |
| **5 — Defects** | Defect taxonomy injection, DF-7 built deliberately | DF-7 test set exists and Checkov scores zero on it |
| **6 — Advisor** | Advisor with grounding rule; iteration loop per FD-02 | Seeded-defect recall measured; **sycophancy test passes** |
| **7 — Recommender** | GNN ranker + baselines; constraint mask | Precision@k, NDCG vs baselines reported |
| **8 — Reconstruction** | Intent reconstruction + calibration | Round-trip fidelity and reliability diagram reported |
| **9 — Explainer** | Subgraph extraction, counterfactuals, three renderings | Fidelity metrics; invariance test passes |
| **10 — Agents** | Agent 2 harvest, Agent 1 plan/apply | End-to-end run completes to T1 in a live account |
| **11 — Evaluation** | Full experiment suite; human study | All C1–C5 evidence collected |
| **12 — Write-up** | Dissertation; demo rehearsal | Submitted |

**Phase 1 is where projects like this stall.** It is tedious, produces nothing demonstrable, and every compliance claim rests on it. Start it before the interesting parts and budget generously.

**Phase 6's exit criterion is a gate, not a checkbox.** If the Advisor fails the sycophancy-resistance test, the architecture needs revisiting before phases 7–11 are built on top of it.

---

## 11. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Scope explosion** — breadth across both courses with depth in neither | **High** | **High** | D2 hard limit: 3 archetypes, 2 frameworks. Refuse additions after Phase 3. |
| Ontology encoding underestimated (Phase 1) | High | High | Start early; timebox; reduce control count before reducing quality |
| Circularity criticism at examination | Medium | High | Four defences pre-built into evaluation (FD-05 §7); lead with C1 and C2 |
| AWS credit exhaustion | Medium | Medium | Plan-only corpus; budget alarms day one; no Neptune; demo-window-only Config/GuardDuty |
| Advisor is vacuous (agrees with everything) | Medium | **Critical** | Phase 6 gate; adversarial corpus in CI; different base model (D8) |
| Human study recruitment fails | Medium | Medium | Internal pool is 3 students + 1 instructor (n ≈ 4); run as a **pilot** at that scale, external practitioners as upside; the appropriate-reliance result stays meaningful at pilot size (FD-06 §9.3) |
| Relational findings prove rare or contrived | Low | **High** | DF-7 generated deliberately and in quantity; C1 is the headline claim and must not rest on a handful of cases |
| Team member unavailability | Medium | Medium | Phase-based plan allows resequencing of 7/8/9 |
| Over-claiming feedback learning with small N | Medium | Medium | FD-03 §7 scoping statement already drafted — use it |

The first row is the one that actually kills projects of this shape. Both courses invite breadth. Resist.

---

## 12. Commercial analysis

### Positioning

Not another CSPM. The wedge is **audit evidence generation** for mid-tier banks, NBFCs, and payment processors who carry the same regulatory obligations as tier-one institutions but cannot staff a forty-person governance function. They currently meet the obligation with consultants and spreadsheets.

Sold as *"produce the justification, automatically, at the moment the decision is made"* — not as *"find your misconfigurations,"* which is a crowded and well-funded market.

### Defensibility

The knowledge graph enriched with an institution's own accepted configurations, waiver history, and architectural conventions becomes progressively harder to replace (FD-03 §2). Generic policy engines accumulate nothing. This is the substantive answer to *why pay for this rather than run Checkov*.

### Ratings

| Dimension | Rating | Reasoning |
|---|---|---|
| **Academic novelty** | 8.5 / 10 | GNN recommenders exist; security knowledge graphs exist. The joint compliance–cost–explainability framing for financial cloud, with intent reconstruction, is thin ground. Workshop-publishable: IEEE CLOUD, CCGrid, XAI or FinTech workshops. |
| **Industrial relevance** | 9 / 10 | Misconfiguration breaches plus DORA and PCI-DSS v4.0 pressure make this board-level. |
| **Monetary upside** | 7 / 10 | Large market, extremely well-funded incumbents. Realistic path is a niche wedge, not displacement. |
| **Investment required** | 9 / 10 *(i.e. very low)* | ~$0–50/month if disciplined. Principal risk is a forgotten always-on service, not compute. |

### Honest commercial caveats

Selling into financial institutions requires SOC 2 and a security review the project cannot produce. The realistic near-term route is an open-source core with a commercial ontology and enterprise governance layer, or acquisition of the approach rather than the product. Say this plainly in the report; an overclaimed commercialisation section is easier to puncture than a modest one.

---

## 13. Related work positioning

| Category | Examples | What they do | Gap this project addresses |
|---|---|---|---|
| CSPM | Wiz, Prisma Cloud, Orca | Detect violations in existing estates | No design-time recommendation; no cost joint-optimisation; limited relational reasoning |
| Policy-as-code | Checkov, tfsec, OPA, Prowler | Rule-based checks on IaC and live config | Single-resource scope; no recommendation; no justification beyond rule text |
| FinOps | CloudHealth, Cloudability | Cost optimisation | Compliance-blind |
| Cloud security graphs | Academic attack-graph literature | Reachability and attack-path analysis | Security-only; no compliance mapping, no cost, no recommendation |
| Config recommenders | Academic autoscaling / right-sizing work | Performance and cost tuning | No compliance dimension, no explanation layer |
| Graph XAI | GNNExplainer, PGExplainer | Explain GNN predictions | Method, not application; no regulated-domain grounding |

**The unoccupied intersection:** design-time recommendation + compliance grounding + cost joint-optimisation + audit-grade explanation, over a graph representation. That intersection is the project.

---

## 14. Glossary

For readers coming to the cloud or AI terminology fresh.

| Term | Meaning |
|---|---|
| **Configuration** | The hundreds of settings choices defining how software runs on AWS — instance types, network placement, permissions, encryption, backups |
| **Knowledge graph** | Data stored as things connected to things, rather than rows in a table. Suits questions that are chains: *can X reach Y through anything?* |
| **Node / edge** | A thing / a relationship between things. The two elements a graph is made of. |
| **IAM** | Identity and Access Management — AWS's permission system. Who may do what to which resource. |
| **VPC / subnet / security group** | Private network, a slice of it, and a firewall rule set. Where a resource sits and what may reach it. |
| **Multi-AZ** | Deployed across multiple physically separate data centres, so one failing does not take the service down |
| **IaC (Infrastructure as Code)** | Infrastructure defined in text files rather than clicked into a console. Reviewable, versionable, repeatable. |
| **Terraform** | The dominant IaC tool. Its `plan` (preview) / `apply` (execute) split is the safety model this project adopts. |
| **Drift** | When live infrastructure diverges from what the code says it should be |
| **CSPM** | Cloud Security Posture Management — tools that scan estates for misconfigurations |
| **PCI-DSS** | Payment Card Industry Data Security Standard. Mandatory for anyone handling card data. |
| **CIS Benchmark** | Consensus security hardening baselines, machine-checkable |
| **NIST 800-53 / OSCAL** | US control catalogue / its machine-readable encoding format |
| **FIBO** | Financial Industry Business Ontology — a formal vocabulary for financial concepts |
| **GNN** | Graph Neural Network — a model that learns over graph structure rather than flat feature vectors |
| **Link prediction** | Predicting whether an edge should exist between two nodes. Here: should this workload connect to this configuration option? |
| **Weak supervision** | Generating training labels programmatically from imperfect rule-based sources rather than by hand |
| **XAI** | Explainable AI — methods that make a model's reasoning inspectable |
| **Counterfactual** | *What would change if this were different?* — the explanation form that supports decisions |
| **Faithfulness** | Whether an explanation reflects the model's actual computation, as opposed to merely sounding convincing |
| **Subgraph** | A portion of a graph. Here: the minimal set of nodes and edges that account for a recommendation. |

---

## 15. References

Consolidated across FD-01 to FD-06. **Verify every entry before citing** — bibliographic details should be checked against the original publications rather than trusted second-hand.

**Standards and frameworks**
1. PCI Security Standards Council. *PCI-DSS v4.0.*
2. CIS. *Amazon Web Services Foundations Benchmark.*
3. NIST. *SP 800-53 Rev. 5*; *OSCAL* (Open Security Controls Assessment Language).
4. AWS. *Well-Architected Framework*; *Security Reference Architecture.*
5. EDM Council. *Financial Industry Business Ontology (FIBO).*
6. EU. *Digital Operational Resilience Act (Regulation 2022/2554).*
7. Institute of Internal Auditors. *The Three Lines Model.*
8. AXELOS. *ITIL 4: Change Enablement.*

**Machine learning and explanation**
9. Ying, Z. et al. (2019). *GNNExplainer.* NeurIPS.
10. Luo, D. et al. (2020). *Parameterized Explainer for Graph Neural Networks.* NeurIPS.
11. Yuan, H. et al. (2022). *Explainability in Graph Neural Networks: A Taxonomic Survey.* IEEE TPAMI.
12. Jacovi, A. & Goldberg, Y. (2020). *Towards Faithfully Interpretable NLP Systems.* ACL.
13. Wachter, S. et al. (2017). *Counterfactual Explanations Without Opening the Black Box.* Harvard JOLT.
14. Lundberg, S. & Lee, S. (2017). *A Unified Approach to Interpreting Model Predictions.* NeurIPS.
15. Schlichtkrull, M. et al. (2018). *Modeling Relational Data with Graph Convolutional Networks.* ESWC.
16. Hamilton, W. et al. (2017). *Inductive Representation Learning on Large Graphs (GraphSAGE).* NeurIPS.

**Data and supervision**
17. Ratner, A. et al. (2017). *Snorkel: Rapid Training Data Creation with Weak Supervision.* VLDB.
18. Ratner, A. et al. (2016). *Data Programming.* NeurIPS.
19. Zhang, J. et al. (2022). *A Survey on Programmatic Weak Supervision.*

**Systems and human factors**
20. Sculley, D. et al. (2015). *Hidden Technical Debt in Machine Learning Systems.* NeurIPS.
21. Bottou, L. et al. (2013). *Counterfactual Reasoning and Learning Systems.* JMLR.
22. Chaney, A. et al. (2018). *How Algorithmic Confounding in Recommendation Systems Increases Homogeneity.* RecSys.
23. Joachims, T. et al. (2017). *Unbiased Learning-to-Rank with Biased Feedback.* WSDM.
24. Bansal, G. et al. (2021). *Does the Whole Exceed its Parts?* CHI.
25. Buçinca, Z. et al. (2021). *To Trust or to Think.* CSCW.
26. Christiano, P. et al. (2017). *Deep RL from Human Preferences.* NeurIPS.

**Iterative refinement**
27. Madaan, A. et al. (2023). *Self-Refine.* NeurIPS.
28. Shinn, N. et al. (2023). *Reflexion.* NeurIPS.
29. Huang, J. et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR.
30. Sharma, M. et al. (2023). *Towards Understanding Sycophancy in Language Models.*

**Tooling**
31. Bridgecrew. *Checkov*; Aqua Security. *tfsec*; Prowler Team. *Prowler.*
32. Rhino Security Labs. *CloudGoat*; Bridgecrew. *TerraGoat*; Summit Route. *flaws.cloud.*
33. HashiCorp. *Terraform.*
