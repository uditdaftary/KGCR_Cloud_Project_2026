# FD-05 — Data Strategy and Corpus Construction

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-05
**Status:** Baseline — resolves D3, proposes resolution for D2
**Depends on:** FD-01, FD-02, FD-03, FD-04

---

## 1. The constraint

No financial institution will supply its cloud configuration data to a student project. That data is a complete map of the institution's attack surface; the request would be refused, correctly, at the first conversation.

This is the project's binding constraint, and the single most common reason comparable projects fail at examination — not because the model is weak, but because the evaluation rests on data whose provenance cannot be defended.

This document specifies how the framework is trained and evaluated without it, and states plainly what that costs in validity.

---

## 2. Reframe: most of the system needs no training data

The problem is smaller than it first appears, because the knowledge graph is **authored, not learned**.

| Component | Origin | Training data required |
|---|---|---|
| L1 — normative layer (controls, clauses, service capabilities, constraints) | Curated from PCI-DSS, NIST 800-53, CIS Benchmarks, AWS documentation, FIBO | **None** |
| Constraint mask (S2) | Deterministic rules over L1 | **None** |
| Advisor grounding (FD-04) | L1 retrieval | **None** |
| Dependency graph construction (S4) | Deterministic over spec | **None** |
| **Recommender ranking (S2)** | Learned | **Yes** |
| **Intent reconstruction (S1c)** | Learned | **Yes** |
| Explainer rendering (S5) | Prompted over findings + graph | Minimal; evaluation data only |

Only two components learn. Everything the compliance argument rests on is curated and auditable — which is itself a defensible design position, not merely a convenience. Compliance logic derived from a statistical model would be far harder to justify to a regulator than compliance logic derived from a citable clause.

The corpus therefore serves a narrow purpose: teach a ranker to prefer good configurations among legal ones, and teach a classifier to recover intent from topology.

---

## 3. Proposed resolution of D2 (scope)

Corpus generation cannot begin until scope is fixed. Recommendation:

**Three workload archetypes**
1. **Payments API** — cardholder data, high throughput, PCI-DSS in scope. The flagship; strictest controls, clearest regulatory hook.
2. **Customer data platform** — PII at rest, analytical access patterns, batch and interactive. Exercises data-flow reachability, where the graph earns its place.
3. **Internal reporting service** — low sensitivity, cost-dominant. The contrast case: demonstrates the framework does not simply maximise controls regardless of context.

**Two compliance frameworks**
- **PCI-DSS v4.0** — narrow, prescriptive, unambiguous mapping to configuration. Ideal for demonstrating traceability.
- **CIS AWS Foundations Benchmark** — broad hardening baseline, machine-checkable, well supported by open tooling.

NIST 800-53 is loaded as a **cross-reference layer** rather than an enforced framework — it gives control-family vocabulary and OSCAL export without tripling the encoding effort.

**Rationale.** Three archetypes is the minimum that demonstrates the system is context-sensitive rather than applying one template; the third archetype is what proves it. Two frameworks demonstrate multi-framework reasoning without the encoding burden of a third. Depth in three archetypes will mark better than breadth across ten — and breadth is the failure mode this project is most exposed to.

---

## 4. Corpus composition

| Source | Volume | Role | Cost |
|---|---|---|---|
| **A. Synthetic estates** | 2,000–5,000 | Training bulk | Compute only |
| **B. Mined public IaC** | ~500 | Real-world irregularity | Free |
| **C. Curated gold set** | 50–100 | Evaluation only, never trained on | Manual effort |
| **D. Adversarial corpora** | ~50 | Detection recall testing | Free |

### A. Synthetic estates

Parameterised Terraform generators emit complete multi-account estates. Each generation samples an intent from the archetype space, renders a configuration, and optionally injects defects from the taxonomy in §5.

Critically, **generation is intent-first**. The intent is sampled, then the configuration is produced from it. This means every synthetic estate carries its originating intent as free ground truth — which is exactly what intent reconstruction (S1c) needs, and it is the reason that contribution is cheaply evaluable (§8).

Parameter axes: account topology, region and AZ spread, service composition, network layout, IAM shape, tagging discipline (including deliberately poor tagging), scale, and injected defect set.

**Stated weakness:** synthetic data reflects the assumptions of whoever wrote the generator. If the generator only produces defects the Advisor can find, evaluation is circular. Sources B and D exist to attack this, and the limitation must be stated in the writeup rather than left for a reviewer to discover.

### B. Mined public IaC

Terraform Registry modules, AWS Solutions Library, `awslabs` and `aws-samples` repositories, public reference implementations. Supplies the irregularity a generator will not invent — inconsistent naming, partial migrations, dead resources, idiosyncratic module structure.

**Licensing.** Only permissively licensed sources (Apache-2.0, MIT, or explicit AWS sample licences). Record licence and provenance per artifact. An academic project that cannot account for the licensing of its corpus has a problem that no amount of model performance repairs.

### C. Curated gold set — evaluation only

50–100 configurations derived from the AWS Well-Architected Framework, the AWS Security Reference Architecture, and published financial-services reference architectures. Hand-verified, hand-labelled, mapped to controls.

**This set is never trained on, at any stage.** It is the regression gate referenced in FD-03 §6 and the false-positive baseline in FD-04 §10 — every CRITICAL raised against it is a false positive by construction, because these configurations are compliant by construction. Contaminating it destroys both functions simultaneously and irrecoverably.

Cost of construction is real: perhaps 40–60 hours of careful manual work. Budget it explicitly. It is the single highest-leverage data investment in the project.

### D. Adversarial corpora

CloudGoat, TerraGoat, flaws.cloud, and comparable deliberately-vulnerable environments. Independently authored known-bad configurations, used purely to measure detection recall. Because the project did not create these defects, recall against them is meaningful evidence in a way that recall against self-injected defects is not.

---

## 5. Defect taxonomy

Injected defects must be enumerated, classed, and mapped to controls in advance. Ad-hoc injection produces an unmeasurable corpus.

| Class | Example defects | Typical severity | Single-resource detectable? |
|---|---|---|---|
| **D1 Exposure** | Public subnet placement, open security group, public S3 ACL, public RDS endpoint | CRITICAL | Yes |
| **D2 Encryption** | Unencrypted volume, unencrypted snapshot, TLS not enforced in transit, no field-level encryption on PAN | CRITICAL | Yes |
| **D3 Identity** | Wildcard IAM policy, cross-account trust to unknown principal, long-lived access keys, missing MFA on privileged roles | CRITICAL / HIGH | Yes |
| **D4 Observability** | CloudTrail disabled, log retention below requirement, no VPC flow logs, unlogged data access | HIGH | Yes |
| **D5 Resilience** | Single-AZ deployment against a multi-AZ target, no backup policy, no cross-region replication where required | HIGH / MEDIUM | Partly |
| **D6 Cost** | Oversized instances, unattached volumes, idle NAT gateways, no lifecycle policy | MEDIUM | Partly |
| **D7 Relational** | Multi-hop exfiltration paths, transitive trust chains, indirect internet reachability, privilege escalation paths | CRITICAL | **No** |

**Class D7 is the one that matters most.** It exists to demonstrate the central architectural claim: that a graph representation detects a defect class that single-resource policy engines cannot reach by construction. Comparative results on D7 are the framework's strongest empirical evidence, and D7 estates should be generated deliberately and in quantity, not left as an emergent by-product.

Each defect instance is recorded with its class, injection site, the control it breaches, and the expected finding — giving per-defect ground truth for the seeded-recall metric in FD-04 §10.

---

## 6. Labelling via weak supervision

Manual labelling of thousands of estates is not feasible. The mechanism instead:

> Run open-source policy engines — **Checkov, tfsec, Prowler, AWS Config managed rules** — across the corpus. Collectively these encode well over a thousand expert-authored rules. Treat each engine as a **programmatic labelling function** in the weak-supervision sense (Ratner et al., Snorkel), and combine their outputs into probabilistic labels, using inter-engine agreement and disagreement as a confidence signal.

This gives a principled and citable answer to the question every examiner asks — *where did your labels come from?* — and reframes what would otherwise look like a shortcut as an established method with a literature behind it.

Two additional benefits fall out. Engine **disagreement** localises genuinely ambiguous configurations, which are exactly the cases that should route to T3 CONTESTED. And engine **coverage gaps** — configurations no engine comments on — identify where the graph must supply judgement that rule engines cannot, which is where the project's contribution lives.

---

## 7. The circularity trap and four defences

**The trap.** Train on Checkov's labels, evaluate against Checkov's labels, and the result is a slower Checkov with a graph attached. This is the most probable line of attack at examination, and it is fatal if unanswered.

Four defences, all of which should be built into the evaluation design from the start rather than retrofitted:

**Defence 1 — Rule holdout.** Train on Checkov and tfsec; evaluate on Prowler rules the model has never seen. Performance on held-out rules measures generalisation beyond memorised patterns rather than reproduction of a known rule set.

**Defence 2 — The task is categorically different.** Policy engines *detect violations in existing configurations*. This framework *recommends configurations for stated intents*. Checkov cannot answer "what should I build for a PCI-scoped payments API at 5k TPS." There is no baseline to be a slower version of, because no rule engine performs this task at all. State this early and directly.

**Defence 3 — Joint objective.** No policy engine trades compliance against cost against resilience. Report **Pareto frontiers**: configurations that are simultaneously compliant *and* cheaper than the naive rule-satisfying baseline. Joint optimisation is a capability rule engines structurally lack.

**Defence 4 — Relational findings (D7).** Single-resource engines score zero on D7 by construction. A comparative table on this class is the cleanest possible demonstration that the graph is load-bearing.

Defences 2 and 4 are the strong ones. Lead with them.

---

## 8. Ground truth for intent reconstruction

Because synthetic generation is intent-first (§4A), the reconstruction evaluation is free and clean:

1. Sample intent `I`.
2. Generate estate `E` from `I`.
3. Discard `I`. Harvest `E` as if it were an unknown production account.
4. Reconstruct `Î` via S1c.
5. Measure per-field recovery of `Î` against `I` — accuracy for categoricals, calibration for confidence scores.

This is a self-contained, reportable experiment requiring no external data, and it evaluates the project's named contribution (FD-01 §7) in isolation from the rest of the pipeline. It should be one of the first experiments run, because it de-risks the most uncertain component early.

**Confidence calibration matters as much as accuracy.** Per FD-01 §7, low-confidence reconstructions must escalate to user confirmation rather than proceed silently. An overconfident reconstructor is more dangerous than an inaccurate one, since the escalation mechanism depends entirely on the confidence estimate being honest. Report reliability diagrams, not just accuracy.

---

## 9. Splits and leakage

| Split | Content | Purpose |
|---|---|---|
| Train | 70% of A + B | Recommender and reconstructor fitting |
| Validation | 15% of A + B | Hyperparameters, hop-bound ablation |
| Test | 15% of A + B | Held-out performance |
| **Gold** | All of C | Regression gate, false-positive baseline. Never trained on. |
| **Adversarial** | All of D | Detection recall. Never trained on. |
| **Relational** | D7 subset of A | Comparative claim against policy engines |

**Split at estate level, never at resource level.** Resource-level splitting leaks: two resources from the same generated estate share topology, tagging conventions, and generator seed, so a model can recognise the estate rather than learn the pattern. Estate-level splitting is the correct unit and should be stated explicitly — reviewers do check this, and it is a common and quietly fatal error.

Additionally: split by **generator seed family** so that structurally near-identical estates cannot straddle train and test.

---

## 10. AWS cost control

Three student accounts, no meaningful credit budget. The corpus is generated as **infrastructure-as-code artifacts, not deployed infrastructure** — Terraform plan output and state representations are sufficient for graph construction and for most of the labelling engines. Nothing needs to run.

| Control | Action |
|---|---|
| Corpus generation | `terraform plan` only; parse plan JSON. No `apply`. |
| Graph store | Neo4j Community on a single small instance, or local for development. **Not Neptune** — it bills continuously and will exhaust credits in days. |
| Continuously-billing services | AWS Config recorders, Security Hub, GuardDuty bill per-resource per-hour. Enable only in Account C, only during demonstration windows, and disable immediately after. |
| Budget alarms | Set on day one, at $5 / $15 / $30, on all three accounts. Not after the first surprise. |
| Live deployment | Reserved exclusively for the end-to-end demonstration — a handful of `apply` runs, torn down immediately |
| Harvest testing | Against a small deliberately-built reference estate in Account A, not against generated corpus estates |

Expected steady-state spend if disciplined: under $20/month. The dominant risk is not compute but a forgotten always-on service — most commonly a Config recorder or a NAT gateway left running after a demo.

---

## 11. Threats to validity

State these in the dissertation. A project that names its own weaknesses reads as more rigorous than one that waits to have them named for it.

| Threat | Severity | Response |
|---|---|---|
| Synthetic data encodes the authors' assumptions about what good configuration looks like | **High** | Sources B and D; adversarial corpus recall reported separately; stated openly |
| Weak-supervision labels inherit policy-engine blind spots | **High** | Rule holdout (Defence 1); gap analysis reported |
| Gold set is small (50–100) | Medium | Reported with confidence intervals; used as a gate, not as a performance headline |
| Three archetypes may not generalise to the wider AWS surface | Medium | Scoped claim: the framework is demonstrated for three archetypes, not claimed universal |
| No real financial-sector validation | **High** | Acknowledged as the principal limitation; expert review (n≈3–5 practitioners) on the gold set is the affordable partial mitigation |
| Cost data is list-price, not negotiated enterprise rates | Low | Stated; relative comparisons remain valid |
| Mined IaC quality is unverified | Low | Used as input diversity, not as ground truth |

The fifth row is the honest headline limitation. The right posture is to state it in the abstract, not bury it — and to note that expert review of the gold set, even at n=3, converts an unvalidated artifact into a partially validated one at almost no cost.

---

## 12. Build sequence

Dependency-ordered. Do not parallelise past a broken step.

1. **Fix D2** (§3) — everything downstream depends on scope
2. **Encode L1** — controls for PCI-DSS and CIS, mapped to AWS service properties. Slow, unglamorous, and the foundation of every compliance claim.
3. **Build the gold set (C)** — small, manual, high value; also validates the L1 encoding
4. **Build the generator** — intent-first, parameterised
5. **Generate corpus A**, without defect injection initially
6. **Wire the labelling pipeline** — Checkov, tfsec, Prowler over plan output
7. **Implement defect injection** per §5, including D7 deliberately
8. **Mine corpus B**, with licence tracking
9. **Import corpus D**
10. **Fix splits** at estate level, freeze the test set

Step 2 is where projects of this type most often stall. It is tedious, it produces nothing demonstrable, and it cannot be skipped — the entire compliance argument, the Advisor's grounding rule (FD-04 §4), and the severity taxonomy (FD-02 §4) all rest on it. Budget generously and start it early.

---

## 13. Open items

| Ref | Item |
|---|---|
| D2 | Scope — recommendation in §3, requires confirmation |
| D11 | Cost data source: AWS Price List API vs static snapshot (snapshot is reproducible, and reproducibility matters more here than currency) |
| D12 | Whether OSCAL is used as the internal control encoding or only as an export format |
| D13 | Expert-review protocol for the gold set — recruitment, instrument, ethics approval if required |

---

## 14. References

1. Ratner, A. et al. (2017). *Snorkel: Rapid Training Data Creation with Weak Supervision.* VLDB — programmatic labelling functions.
2. Ratner, A. et al. (2016). *Data Programming: Creating Large Training Sets, Quickly.* NeurIPS.
3. Zhang, J. et al. (2022). *A Survey on Programmatic Weak Supervision.* — label-model combination methods.
4. AWS. *Well-Architected Framework* and *Security Reference Architecture* — gold-set source.
5. CIS. *Amazon Web Services Foundations Benchmark* — hardening baseline.
6. PCI Security Standards Council. *PCI-DSS v4.0*.
7. NIST SP 800-53 Rev. 5 and *OSCAL* — cross-reference layer and export encoding.
8. Bridgecrew. *Checkov*; Aqua Security. *tfsec*; Prowler Team. *Prowler* — labelling functions.
9. Rhino Security Labs. *CloudGoat*; Bridgecrew. *TerraGoat*; Summit Route. *flaws.cloud* — adversarial corpora.
10. EDM Council. *Financial Industry Business Ontology (FIBO)* — domain ontology layer.
