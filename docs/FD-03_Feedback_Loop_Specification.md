# FD-03 — Feedback Capture and Graph Enrichment

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-03
**Status:** Baseline
**Governs:** Stage S11 of FD-01, and all learning signal into the knowledge graph
**Depends on:** FD-01, FD-02

---

## 1. Purpose

In the original flowcharts, both conditions terminated at STOP. Every decision the user made — what they accepted, what they rejected, what they edited and how — was discarded at that point.

That discarded data is the most valuable signal the system produces. This document specifies what is captured, how it enters the knowledge graph without contaminating curated ground truth, what it is legitimately used for, and the pathologies that must be guarded against.

---

## 2. Why this matters more than it appears

Three arguments, in increasing order of importance to the project.

**Engineering.** Without captured runs there is no way to answer basic operational questions: how often does the advisor converge on pass 1, what proportion of recommendations are accepted unmodified, which controls generate the most contested findings.

**Research.** User edits at S8 are *human corrections to model output*, produced by domain practitioners at no annotation cost. This is a preference dataset generated as a by-product of normal use — the same structural resource that makes preference learning viable in other domains. Given that acquiring real financial-sector configuration data is the project's hardest constraint (D3), a mechanism that manufactures labelled signal from ordinary operation is disproportionately valuable.

**Commercial.** A system whose recommendations improve with organisational use accumulates a defensible asset. Generic policy engines do not do this. The knowledge graph, enriched with an institution's own accepted and rejected configurations, its waiver history, and its architectural conventions, becomes progressively harder to replace. This is the substantive answer to "why would a bank pay for this rather than use Checkov" and belongs in the monetisation chapter.

---

## 3. Signal taxonomy

Five classes, ranked by information value.

### Class 1 — User edits at S8 *(highest value)*
The user accepted the shape of the recommendation but changed specifics. The delta is a precise, localised correction: the model was right about everything except this. Captured as a structural diff over the spec plus optional free-text reason.

Highest value because it is dense and unambiguous. A rejection tells you something is wrong; an edit tells you exactly what and exactly what it should have been.

### Class 2 — Outright rejections at S8
The user declined without editing. Weaker signal — the reason is unstated — so the CLI should prompt for a reason code (`too-expensive`, `over-engineered`, `violates-internal-standard`, `wrong-intent`, `other`). The `wrong-intent` code is the critical one in review mode: it indicates a failed intent reconstruction (S1c), not a failed recommendation, and must be routed to a different improvement path.

### Class 3 — Advisor loop traces
Full pass-by-pass record from FD-02: findings raised, findings resolved, spec hashes, halt reason. Feeds recommender improvement — a finding raised repeatedly across many runs indicates a systematic recommender weakness, not a one-off.

### Class 4 — Post-apply drift
After T1 DEPLOYED, the estate is re-harvested on a schedule and compared against the deployed spec. Divergence means either the recommendation was operationally unworkable and someone changed it by hand, or configuration drift occurred.

This is the only signal class grounded in *reality* rather than in opinion. Everything else records what humans and models thought; drift records what actually survived contact with production. It is the strongest available correction to a system that could otherwise learn purely from its own and its users' preferences.

### Class 5 — Attestation and contested outcomes
T2 and T3 terminals. Contested findings clustering on particular controls indicate ambiguity in the control encoding itself — a maintenance signal for the graph rather than for the models.

---

## 4. The run record

One record per run, written at every terminal state (INV-4).

```json
{
  "run_id": "uuid",
  "timestamp": "ISO-8601",
  "mode": "design | review",
  "audience": "architect | auditor | learner",
  "actor": { "user_ref": "pseudonymous-id", "role": "architect | auditor | student" },

  "intent": {
    "source": "stated | reconstructed",
    "workload_archetype": "...",
    "data_classification": "...",
    "regulatory_scope": ["PCI-DSS-v4"],
    "availability_target": "...",
    "budget_ceiling": "...",
    "reconstruction_confidence": { "workload_archetype": 0.87, "...": "..." }
  },

  "recommendation": {
    "spec_id": "...",
    "spec_hash": "...",
    "candidates_considered": 12,
    "rank_of_selected": 1,
    "estimated_monthly_cost": 412.50,
    "masked_by_constraints": 3
  },

  "advisor": {
    "passes_executed": 2,
    "halt_reason": "CONVERGED",
    "findings": [ { "id": "F-003", "severity": "HIGH", "control_ref": "CIS-2.1.1",
                    "raised_pass": 1, "resolved_pass": 2, "resolution": "patched" } ],
    "waivers": []
  },

  "explanation": {
    "bundle_id": "...",
    "subgraph_node_count": 47,
    "counterfactuals_offered": 3
  },

  "differential": {
    "observed_graph_id": "...",
    "divergences": 8,
    "violations": 2,
    "relational_violations": 1
  },

  "disposition": {
    "terminal_state": "DEPLOYED",
    "acceptance_cycles": 2,
    "user_edits": [
      { "cycle": 1, "path": "compute.instance_type",
        "from": "m6i.2xlarge", "to": "m6i.xlarge",
        "reason_code": "too-expensive", "note": "burst profile, not sustained" }
    ],
    "rejection_reason_code": null,
    "time_to_disposition_seconds": 340
  },

  "outcome": {
    "plan_id": "...",
    "applied": true,
    "apply_errors": [],
    "drift_checks": [ { "at": "ISO-8601", "divergences": 0 } ]
  }
}
```

**Design note.** Records are append-only and immutable. A revised recommendation is a new run linked by `supersedes`. Mutable history is unusable as audit evidence, and audit evidence is the product.

---

## 5. Graph enrichment — the layering rule

The single most important constraint in this document:

> **Observed and behavioural data must never be written into the normative layer of the knowledge graph.**

The graph carries three provenance-separated layers.

| Layer | Contents | Source | Mutable by feedback? |
|---|---|---|---|
| **L1 — Normative** | Controls, clauses, service capabilities, hard constraints | Curated from PCI-DSS, NIST 800-53, CIS, AWS documentation | **No** |
| **L2 — Observed** | Harvested estates, deployed configurations, drift history | Agent 2, post-apply checks | Yes, append-only |
| **L3 — Behavioural** | Accept/reject decisions, edits, waivers, contested outcomes | Run records | Yes, append-only |

Every node and edge carries a provenance tag identifying its layer and source.

**Why this is non-negotiable.** If organisational behaviour can rewrite the normative layer, then an institution that habitually accepts a non-compliant pattern will, over time, teach the system that the pattern is compliant. The framework would launder a bad habit into an apparent standard — the precise inverse of its purpose. PCI-DSS Requirement 3.4 does not become negotiable because a hundred engineers clicked accept.

Behaviour therefore informs **ranking and defaults** only. It never touches **legality**. Stated formally:

- L1 determines what is *permitted*.
- L2 and L3 influence what is *preferred* among permitted options.

This is a clean, defensible separation and should be presented as a named architectural principle in both course submissions. It is also the answer to the obvious examiner question: *what stops your system from learning bad practice?*

---

## 6. Learning uses

| Signal | Consumed by | Mechanism |
|---|---|---|
| User edits (C1) | Recommender | Preference pairs: `(intent, rejected_option) < (intent, edited_option)`. Directly usable for pairwise ranking objectives. |
| Rejections (C2), reason-coded | Recommender / intent module | `wrong-intent` → intent reconstruction training set. All others → negative examples for ranking. |
| Advisor traces (C3) | Recommender | Findings recurring across runs identify systematic weaknesses; the associated configurations become hard negatives. |
| Drift (C4) | Recommender + evaluation | Configurations that survive unmodified in production are validated positives. Ground-truth correction against preference drift. |
| Contested clusters (C5) | Ontology maintenance | Human review of control encodings that repeatedly produce irresolvable disagreement. |

**Retraining cadence.** Batch, not online. Online learning from user feedback in a compliance-adjacent system is dangerous — a single anomalous session should never shift recommendations. Batch retraining with a held-out gold set (FD-05) as a regression gate: if performance on the curated reference architectures degrades, the update is rejected.

---

## 7. Pathologies and mitigations

Feedback loops in deployed decision systems are known to produce specific failure modes. Each must be addressed explicitly; doing so is itself a contribution, since most applied-ML student projects do not.

| Pathology | Manifestation here | Mitigation |
|---|---|---|
| **Self-confirmation / echo chamber** | System recommends X, user accepts X, system learns X is good, recommends X more. Confidence rises without evidence. | Anchor evaluation on the held-out gold set, never on accepted-recommendation rate. Track *diversity* of recommendations over time; collapsing diversity is an alarm. |
| **Presentation bias** | Only ranked-top options are ever seen, so only they can be accepted. Lower-ranked options accumulate no evidence. | Log full candidate sets, not just the selected one. Occasionally surface the second-ranked option with its trade-off (also good UX for the learner persona). Treat accepts as biased-sample data, not as random-sample data. |
| **Bad-practice laundering** | Organisational habit erodes compliance standards | L1/L3 separation (§5) — structurally prevented, not merely discouraged |
| **Feedback entanglement (CACE)** | Changing any input signal changes everything downstream in opaque ways | Version the graph; pin model versions in run records; make every recommendation reproducible from `(spec_hash, graph_version, model_version)` |
| **Drift-as-signal misread** | Manual post-deploy changes recorded as "recommendation was wrong" when the real cause was an unrelated incident | Do not auto-ingest drift as a negative. Flag for human triage; only triaged drift enters training. |
| **Small-N overfitting** | A student project's few hundred real runs are not a training set | Feedback is used to *reweight* and to evaluate, not to train from scratch. Be explicit about this limitation in the writeup rather than implying an unearned scale. |

**Honest scoping statement for the dissertation.** Within a semester the framework will not accumulate enough real runs for feedback learning to demonstrate measurable improvement. The correct claim is therefore architectural: the mechanism is specified, instrumented, and validated on simulated feedback traces, with real-world efficacy identified as future work. Claiming demonstrated improvement from a few dozen runs would be indefensible and is easily caught.

---

## 8. Simulated feedback evaluation

To evaluate the mechanism without a production user base:

1. Generate synthetic user policies (cost-averse, availability-maximising, standards-conservative) as programmatic personas.
2. Run the pipeline over the synthetic corpus with each persona acting at S8 under its policy.
3. Apply the feedback loop.
4. Measure whether recommendations converge toward each persona's revealed preference *while* the held-out gold-set compliance score remains flat.

The second half is the real result. Personalisation that degrades compliance is a failure regardless of how well it personalises — and demonstrating that the L1 barrier holds under adversarial persona pressure is a strong, cheap experiment.

---

## 9. Governance and privacy

Financial configuration data is sensitive. Even in an academic build, the governance posture must be designed in, because it is a precondition for any commercial conversation.

| Control | Requirement |
|---|---|
| **Tenancy isolation** | L2 and L3 data are partitioned per organisation. No cross-tenant inference by default. |
| **Cross-tenant learning** | Opt-in only, and only over abstracted patterns — never raw identifiers, ARNs, account numbers, or IP ranges. |
| **Pseudonymisation** | User references are pseudonymous in run records; the mapping is held separately. |
| **Retention** | Run records retained per audit requirement (7 years is the typical financial-sector figure); training extracts held separately with a shorter lifecycle. |
| **Right to exclusion** | An organisation can withdraw its runs from training without losing its audit history — hence the separation of the two stores. |
| **Sensitivity of the graph itself** | An enriched estate graph is a complete map of an institution's cloud attack surface. It requires the same protection as production credentials. Encryption at rest, strict access control, and full access audit logging. |

The last row deserves a paragraph of its own in the dissertation. The framework's value and its risk share a source: a graph rich enough to reason about reachability is a graph rich enough to attack from. Naming this candidly is better scholarship than omitting it, and reviewers will notice its absence.

---

## 10. Instrumentation summary

| Metric | Interpretation |
|---|---|
| Acceptance rate (unmodified) | Recommender quality — but see presentation bias |
| Edit rate and mean edit distance | Near-miss rate; falling distance over time is the improvement signal |
| Rejection reason distribution | Diagnostic routing between recommender and intent module |
| Acceptance cycles per run | User-facing friction |
| Drift rate at 7 / 30 days | Operational realism of recommendations |
| Recommendation diversity index over time | Echo-chamber alarm |
| Gold-set compliance score per model version | Regression gate; must never fall |

---

## 11. References

1. Sculley, D. et al. (2015). *Hidden Technical Debt in Machine Learning Systems.* NeurIPS — feedback loops, entanglement, the CACE principle.
2. Bottou, L. et al. (2013). *Counterfactual Reasoning and Learning Systems.* JMLR — learning from logged decisions in deployed systems.
3. Chaney, A., Stewart, B., Engelhardt, B. (2018). *How Algorithmic Confounding in Recommendation Systems Increases Homogeneity and Decreases Utility.* RecSys — echo-chamber dynamics.
4. Joachims, T. et al. (2017). *Unbiased Learning-to-Rank with Biased Feedback.* WSDM — presentation bias in implicit feedback.
5. Christiano, P. et al. (2017). *Deep Reinforcement Learning from Human Preferences.* NeurIPS — preference-pair learning from human comparisons.
6. NIST OSCAL — machine-readable assessment results; candidate export format for run records.
7. EU DORA (Regulation 2022/2554) and PCI-DSS v4.0 — retention and evidence obligations informing §9.
