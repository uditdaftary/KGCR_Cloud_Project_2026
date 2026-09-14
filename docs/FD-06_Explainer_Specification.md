# FD-06 — Explainer Specification

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-06
**Status:** Baseline — resolves D1 (audience model)
**Governs:** Stage S5 of FD-01, and the `kgcr explain` command
**Depends on:** FD-01, FD-02, FD-04

---

## 1. Purpose

The Explainer converts a converged specification, its dependency graph, and its advisor findings into a justification a human can check.

This is the component the project is named for, and it is where the framework's central claim is either earned or lost. The claim is that **the explanation is not generated after the fact — it is the reasoning path itself, extracted from the graph.** If the Explainer is implemented as a language model narrating a conclusion it did not participate in producing, the project reduces to a chatbot with a database, and the "explainable AI" framing becomes decoration.

---

## 2. Position and boundaries

The Explainer runs on **both** paths (a change from the original flowcharts, FD-01 §4). A newly designed configuration must be defensible to an auditor exactly as much as an inherited one; explanation is not a defect-reporting feature.

| | Advisor (FD-04) | Explainer (this document) |
|---|---|---|
| Question | What is wrong with this? | Why is this defensible? |
| Stance | Adversarial | Expository |
| Can block deployment | Yes | No |
| Audience-aware | No | **Yes** — three modes |
| Sees others' rationale | No (INV-7) | Yes — both |
| Grounded in | L1 only | L1 + findings + dependency graph + L3 (counterfactual ranking only, §6) |

The Explainer is the only component permitted to see everything, precisely because it has no authority. It cannot block, cannot modify, and cannot influence the recommendation. It reports.

---

## 3. What counts as an explanation here

Four components per recommended element. All four are required; an explanation missing any of them is incomplete.

| Component | Content | Source |
|---|---|---|
| **Justification** | The minimal subgraph establishing why this element is present | Subgraph extraction (§5) |
| **Provenance** | The control clause(s) the element satisfies, with citable reference | L1 nodes |
| **Consequence** | Cost and risk delta attributable to the element | L1 cost facts + finding severities |
| **Counterfactual** | What changes if the element is removed or altered | Constrained re-evaluation (§6) |

The counterfactual is what converts an explanation from a description into a decision aid. *"Multi-AZ is present because control X requires it"* tells an architect nothing actionable. *"Removing the standby saves $180/month and forfeits control X, moving the estate from compliant to non-compliant under PCI-DSS 12.10"* lets them decide.

---

## 4. Invariant INV-2, formalised

> The audience flag changes **rendering only**. The underlying subgraph, findings, control references, and conclusions are identical across all three renderings.

Formally: let `B` be the ExplanationBundle and `R_a` the rendering function for audience `a`. Then for all audiences `a, a'`:

```
content(R_a(B)) ≡ content(R_a'(B))    under semantic equivalence of claims
```

Only surface form, vocabulary, level of abstraction, and ordering may differ.

**Why this is non-negotiable.** If audience alters what the system concludes, the system is performing persuasion rather than explanation — telling each reader what that reader is disposed to accept. In a compliance context this is not a quality issue, it is a fabrication of assurance. An auditor and an architect reading the same run must be able to compare notes and find no contradiction.

**This must be tested, not asserted.** §9 specifies the invariance test. It is a strong result to be able to report, and its absence will be noticed.

---

## 5. Subgraph extraction

The justification substrate is a **minimal sufficient subgraph**: the smallest set of nodes and edges whose presence accounts for the recommendation of a given element.

**Method.** For learned components (the recommender's ranking), apply GNNExplainer- or PGExplainer-style mask optimisation to identify the edges and node features whose removal most degrades the prediction. For rule-derived elements (anything produced by the constraint mask or raised by the Advisor), the justification is the **deterministic evidence path** already carried in the finding's `evidence_path` field (FD-04 §3) — no learned extraction needed, and it is exact rather than approximate.

Two properties are required, and they trade against each other:

- **Sufficiency** — the subgraph alone is enough to establish the recommendation.
- **Minimality** — no proper subset is sufficient.

Report the trade-off explicitly as a sparsity–fidelity curve rather than fixing one operating point. A large subgraph is faithful but unreadable; a small one is readable but may omit the actual cause.

**A point worth making prominently in the dissertation:** for the majority of elements in this system, explanation requires no learned extraction at all, because the reasoning was symbolic. This is a direct consequence of the architecture — the compliance logic is curated (FD-05 §2), not learned — and it is why explanations here can be *exact* where most XAI work must settle for *approximate*. Learned extraction is needed only for the ranking preference among already-legal options. That is a genuinely strong position and most comparable work cannot claim it.

---

## 6. Counterfactual generation

Counterfactuals are produced by **constrained re-evaluation**, not by asking a model to imagine one:

1. Perturb the specification (remove element, downgrade tier, collapse an AZ, widen a policy).
2. Re-run the constraint mask and the relevant control checks.
3. Recompute cost from L1 cost facts.
4. Report the delta only if the perturbation is *minimal* — a single coherent change.

This guarantees counterfactuals are **actionable and true**, because they are evaluated by the same machinery that evaluated the original. A generated counterfactual would be neither.

Cap at three counterfactuals per run by default, selected by decision relevance: the largest cost saving, the largest risk reduction, and the change the user is most likely to attempt anyway (derived from L3 edit history where available, per FD-03).

---

## 7. The language model's role

**The LLM is a verbaliser. It has no reasoning authority.**

Its input is a fully-formed ExplanationBundle. Its task is to render that bundle in the register appropriate to the audience. It may not introduce a fact, a control reference, a number, or a causal claim that is not present in the bundle.

Enforcement is post-hoc and mechanical, because prompting alone is not a control (the same argument as FD-04 §8):

| Check | Action on failure |
|---|---|
| Every control reference in the prose resolves to a `control_ref` in the bundle | Reject and regenerate |
| Every numeric claim matches a bundle value within tolerance | Reject and regenerate |
| No causal claim without a corresponding edge in the justification subgraph | Flag for review |
| Claim set is semantically equivalent across the three renderings | Fail the run's invariance check (§9) |

Framing the LLM as presentation rather than reasoning is what protects the project from the most common criticism levelled at LLM-based systems in regulated domains. It should be stated early and defended, not buried in an implementation note.

---

## 8. Audience renderings

Resolves D1. One pipeline, three renderings.

| Mode | Reader | Register | Emphasis |
|---|---|---|---|
| `architect` | Cloud engineer | Resource-level, terse, assumes AWS fluency | Trade-offs, IaC fragments, dependency ordering, cost deltas |
| `auditor` | Compliance / risk officer | Control-first, minimal AWS jargon, evidence-oriented | Control-to-configuration mapping, evidence trail, coverage gaps, waivers |
| `learner` | Student / new joiner | Expanded, definitional | *Why the control exists*, expanded acronyms, conceptual framing before specifics |

### Worked example — one finding, three renderings

Source: finding F-002 from FD-04 §12 (relational exfiltration path, PCI-DSS 1.3).

**`architect`**
> `app-exec` role holds `s3:GetObject` on `*`, reaching `cardholder-backups`. The role is attached to instances in `subnet-public-1a`, which routes `0.0.0.0/0` via `igw-04b2`. Three-hop path from cardholder data to internet egress. Scope the policy to the two required bucket ARNs, or move the instances to a private subnet with a NAT egress path. Policy scoping is the cheaper fix; NAT adds ~$32/month.

**`auditor`**
> PCI-DSS v4.0 Requirement 1.3 restricts inbound and outbound traffic to the cardholder data environment. This configuration does not meet that requirement. Cardholder data held in the backup store is reachable, through a chain of three configuration relationships, from compute resources that have unrestricted outbound internet access. No single component is individually misconfigured; the exposure arises from their combination. Evidence path and remediation options are attached. Severity: Critical — deployment blocked pending resolution.

**`learner`**
> This is flagged as a **relational** finding, which means every individual setting here looks fine on its own — the problem only appears when you follow the connections between them.
>
> The chain: the application's permission grant (an *IAM role*) allows reading from any storage bucket, including the one holding cardholder backups. That application runs on servers placed in a *public subnet*, meaning they can send traffic directly to the internet. Put together, data that should never leave the secure zone sits on a path that reaches the open internet in three steps.
>
> PCI-DSS Requirement 1.3 exists to prevent exactly this. The rule is not about any one setting being wrong; it is about the cardholder environment having no unintended route in or out. This is the kind of defect a checklist-based scanner tends to miss, because a checklist examines one resource at a time.

**Verify against INV-2.** All three assert: the same control, the same three-hop path, the same severity, the same remediation directions. Vocabulary, ordering, and abstraction differ. Nothing else does.

This example should appear as a figure in both course submissions. It demonstrates the audience model, the relational finding class, and the graph's necessity in a single artifact.

---

## 9. Evaluation

### 9.1 Faithfulness (automated)

| Metric | Definition |
|---|---|
| **Fidelity+** | Prediction change when the justification subgraph is removed. Higher is better. |
| **Fidelity−** | Prediction change when everything *except* the subgraph is removed. Lower is better. |
| **Sparsity** | Subgraph size relative to the full computation graph |
| **Counterfactual validity** | Proportion of generated counterfactuals that, when applied, produce the predicted outcome. Should be ~100%, since they are computed rather than generated. |
| **Verbalisation fidelity** | Proportion of LLM-rendered claims traceable to a bundle field (§7) |

### 9.2 Cross-audience invariance (automated)

Extract the claim set from each of the three renderings of the same bundle; assert semantic equivalence. Any divergence is a defect, not a stylistic variation. **Report the pass rate as a headline result** — it is the empirical form of INV-2, and it is unusual enough to be worth foregrounding.

### 9.3 Human study

The XAI evaluation. Design:

- **n ≈ 4 (pilot): 3 students + 1 instructor**, stratified across expertise levels (student / practitioner). This is the available internal pool (D17); external practitioner recruitment toward n ≈ 10–15 is upside, not a precondition. Report explicitly as a pilot — the appropriate-reliance measure below stays meaningful at this scale, and a pilot honestly labelled is more defensible than an over-claimed study.
- **Within-subject on scenario, between-subject on audience mode.** Each participant sees several findings; audience mode is assigned rather than chosen, so the comparison is not confounded by self-selection.
- **Measures:**
  - *Comprehension* — can the participant correctly restate the defect and its cause?
  - *Appropriate reliance* — inject a small number of **deliberately incorrect** recommendations. Do participants catch them? An explanation that increases trust in wrong answers is a harmful explanation, and this is the measure most XAI evaluations omit.
  - *Perceived trust* — Likert, reported but not treated as the primary outcome.
  - *Time to decision.*
- **Ethics:** institutional approval if required; informed consent; no personal data retained.

Appropriate reliance is the measure worth building the study around. Comprehension and trust scores are easy to move and tell you little; whether an explanation helps a human catch a model's mistake is the question that matters, and a negative result there would be a genuinely valuable finding rather than a failure.

---

## 10. Persistence and export

Explanation bundles are **persisted, never regenerated**. `kgcr explain --run <id>` re-emits the stored bundle in any audience mode.

The reason is evidentiary. If an auditor requests the justification for a configuration deployed eight months ago, regenerating it against a since-updated graph and a since-updated model would produce a different answer — and an audit trail that changes when re-queried is not an audit trail. Bundles are immutable and versioned alongside `(spec_hash, graph_version, model_version)` per FD-03 §7.

**Export target:** NIST OSCAL `assessment-results`, which is the machine-readable format existing GRC tooling already ingests. Cheap to produce once controls are OSCAL-encoded, and it converts the framework from a standalone tool into something that plugs into an institution's existing compliance stack — a material point for the commercial argument.

---

## 11. Failure modes

| Mode | Symptom | Mitigation |
|---|---|---|
| **Post-hoc rationalisation** | Explanation does not correspond to the actual computation | Fidelity metrics; symbolic paths for rule-derived elements |
| **Persuasive explanation** | Fluent prose increases confidence in incorrect recommendations | Appropriate-reliance measure (§9.3); verbalisation fidelity checks |
| **Audience drift** | Renderings diverge in substance | Invariance test (§9.2), run in CI |
| **Explanation overload** | Faithful but unreadable subgraphs | Sparsity–fidelity curve; audience-appropriate truncation with a "full evidence" flag |
| **Counterfactual infeasibility** | Suggested alternative is not actually deployable | Counterfactuals re-evaluated through the constraint mask, not generated |
| **Stale re-emission** | Regenerated explanation contradicts the original | Immutable persistence (§10) |

---

## 12. Open items

| Ref | Item |
|---|---|
| D14 | **Resolved** — sparsity–fidelity curve (§5), then: auditor = max evidence, architect = knee, learner = knee + definitional expansion |
| D15 | **Resolved** — `learner` is a demonstration feature, not a human-study arm. Ingesting new data and having the models learn from it is the FD-03 enrichment loop's job (append-only L2/L3, batch retrain with the gold-set regression gate); that ingestion path is to be kept low-friction so learner demos can be fed new examples easily |
| D12 | OSCAL as internal encoding vs export-only — **resolved export-only** in FD-07 §9 (previously tracked here as the duplicate D16) |
| D17 | **Resolved** — internal pool is 3 students + 1 instructor (n ≈ 4); run as a pilot (§9.3), external practitioners as upside |

---

## 13. References

1. Ying, Z. et al. (2019). *GNNExplainer: Generating Explanations for Graph Neural Networks.* NeurIPS.
2. Luo, D. et al. (2020). *Parameterized Explainer for Graph Neural Network (PGExplainer).* NeurIPS.
3. Yuan, H. et al. (2022). *Explainability in Graph Neural Networks: A Taxonomic Survey.* IEEE TPAMI — fidelity and sparsity metrics.
4. Jacovi, A. & Goldberg, Y. (2020). *Towards Faithfully Interpretable NLP Systems: How Should We Define and Evaluate Faithfulness?* ACL — faithfulness versus plausibility.
5. Bansal, G. et al. (2021). *Does the Whole Exceed its Parts? The Effect of AI Explanations on Complementary Team Performance.* CHI — appropriate reliance.
6. Buçinca, Z. et al. (2021). *To Trust or to Think: Cognitive Forcing Interventions Reduce Overreliance on AI.* CSCW.
7. Wachter, S., Mittelstadt, B., Russell, C. (2017). *Counterfactual Explanations Without Opening the Black Box.* Harvard JOLT.
8. Lundberg, S. & Lee, S. (2017). *A Unified Approach to Interpreting Model Predictions (SHAP).* NeurIPS — comparison baseline for cost-feature attribution.
9. NIST. *OSCAL Assessment Results Model.*
