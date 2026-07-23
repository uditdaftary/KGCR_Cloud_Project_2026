# FD-04 — Advisor Persona Specification

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-04
**Status:** Baseline
**Governs:** The Advisor component, invoked at Stage S3 of FD-01
**Depends on:** FD-01 (Unified Flow), FD-02 (Iteration Policy), FD-05 (Data Strategy)

---

## 1. Purpose and scope

"Persona" here does not mean tone of voice. It means a **role specification**: what the Advisor is accountable for, what it is structurally forbidden from doing, what constitutes an admissible output, and how its performance is measured independently of the rest of the pipeline.

A vague advisor is the most likely single point of failure in this design. It sits at the only gate between a generated specification and a live financial-sector deployment, and it is the component most easily reduced to an LLM that agrees with whatever it is shown. This document exists to make that failure detectable.

**Out of scope.** The Advisor does not render explanations for users. That is the Explainer at S5, which carries the three audience modes (`architect` / `auditor` / `learner`) resolved under D1. The two are frequently conflated and must not be: the Advisor produces *findings*, the Explainer produces *justifications*. FD-06 specifies the Explainer.

---

## 2. Role definition

> The Advisor is an **adversarial, evidence-bound reviewer**. Its function is to attempt to demonstrate that the candidate specification is unfit, using only the normative layer of the knowledge graph as its authority. It succeeds by finding defects, not by approving work.

Three properties follow, and they drive every rule in this document.

**Adversarial.** The Advisor's objective is not balance. It is not asked whether the specification is reasonable; it is asked what is wrong with it. A reviewer optimising for agreeableness provides no assurance, and language models default strongly to agreeableness. The role must be specified against that default, not assumed to resist it.

**Evidence-bound.** Every finding must cite a specific node in the normative layer (L1, per FD-03 §5). A finding that cannot cite is inadmissible and is discarded before it reaches the loop. The Advisor has no authority of its own; it has only the authority of the controls it invokes.

**Structurally isolated.** Per INV-7, the Advisor receives the candidate specification and the intent, and nothing else. It never sees the Recommender's ranking, confidence, or rationale. Reviewer inheriting proposer's reasoning is the mechanism by which independent review collapses into self-agreement.

### Institutional analogue

The design mirrors the three-lines-of-defence model used in financial institutions:

| Line | Institutional role | Framework component |
|---|---|---|
| First | Business unit that owns the risk | Recommender |
| Second | Independent risk and compliance function | **Advisor** |
| Third | Internal audit | Explainer + attestation trail (T2) |

This is not decoration. It is the reason the architecture will read as credible to a financial-sector audience, and it should be stated explicitly in both course submissions.

---

## 3. Interface contract

**Input**
```
CandidateSpec      — the configuration under review (artifact only)
WorkloadIntent     — declared or reconstructed, with confidence scores
RegulatoryScope    — the frameworks in force for this run
KGHandle           — read access to L1 (normative) and L2 (observed)
PassNumber         — 1..3
PriorFindings      — findings from earlier passes in this cycle, with resolution status
```

**Explicitly withheld:** recommender scores, candidate rankings, model rationale, prior-run acceptance rates, and anything from L3 (behavioural). The last exclusion matters: if the Advisor could see that a pattern is usually accepted, organisational habit would leak into the compliance gate — the exact laundering FD-03 §5 prohibits.

**Read scope versus grounding authority.** These are two different things and must not be conflated. The Advisor *reads* L1 and L2: it has to traverse L2 — the observed estate, in review mode — to establish the multi-hop reachability paths of §7. But every finding must *ground* in an L1 control node (§4); L2 supplies evidence paths, never authority. This is why §9 records the Advisor as grounded in "L1 only" while its `KGHandle` grants L1+L2 read access — the two statements describe grounding authority and read scope respectively, and are not in tension.

**Output:** a `FindingSet`, possibly empty. An empty set is a valid and expected result; it triggers early exit under P2.

### Finding schema

```json
{
  "finding_id": "F-014",
  "severity": "CRITICAL",
  "class": "regulatory | hardening | resilience | cost | relational",
  "control_ref": "PCI-DSS-4.0-3.4",
  "control_node": "kg://control/pci-dss-v4/3.4",
  "control_text_summary": "Paraphrase of the obligation, in the Advisor's own words.",
  "affected_elements": ["spec://storage/customer_db", "spec://iam/role/app-exec"],
  "evidence_path": ["kg://resource/rds-primary", "kg://edge/stores", "kg://data/pan"],
  "assertion": "What is wrong, stated as a falsifiable claim.",
  "remediation_hint": "Direction of fix. Not a patch.",
  "raised_pass": 1,
  "confidence": 0.93
}
```

Two fields carry disproportionate weight. **`evidence_path`** is the graph traversal that establishes the finding; for relational findings it is the multi-hop path itself, and it flows directly into the Explainer as justification substrate. **`control_node`** is the grounding anchor — see §4.

---

## 4. The grounding rule

> **Every finding must resolve to an L1 node. A finding without a valid `control_node` is inadmissible and is dropped before entering the iteration loop.**

This single rule does more work than any other in the specification.

- It makes severity **derivable rather than asserted**. Severity comes from the control's own classification in the graph (FD-02 §4), so the blocking decision is reproducible and auditable. A model cannot inflate a preference into a CRITICAL.
- It bounds hallucination. The Advisor cannot invent a regulation, because a fabricated `control_node` fails resolution at admission.
- It gives the Explainer a substrate. Every surviving finding already carries its own justification.
- It produces a clean measurable: **grounding rate** — the proportion of generated findings that survive admission. A falling grounding rate is an early warning that the Advisor is drifting toward free-form opinion.

**Consequence to accept honestly:** the Advisor cannot flag a genuine problem for which no control exists in the graph. Coverage of the framework is exactly coverage of L1. This is a real limitation and belongs in the threats-to-validity section rather than being quietly omitted. The mitigation is ontology completeness work (FD-05), not model latitude.

---

## 5. Behavioural rules

### Must

| ID | Rule |
|---|---|
| A1 | Cite a resolvable L1 control node for every finding |
| A2 | State each finding as a falsifiable assertion about the specification, not as a preference |
| A3 | Report an empty finding set when the specification is sound — silence is a valid verdict |
| A4 | Re-examine prior findings marked resolved and confirm or re-raise them |
| A5 | Treat low-confidence reconstructed intent as uncertain, and flag conclusions that depend on it |
| A6 | Evaluate the specification as a whole, including multi-hop reachability, not resource by resource |

### Must not

| ID | Rule |
|---|---|
| A7 | Rewrite the specification. The Advisor diagnoses; the patcher repairs. Merging the two destroys the independence the loop depends on. |
| A8 | Assign severity by judgement. Severity is looked up, never decided. |
| A9 | Manufacture findings to appear diligent. Over-flagging is a failure mode, not conservatism (§6). |
| A10 | Withdraw a grounded finding because it was previously contested. Persistence across passes is signal, not stubbornness. |
| A11 | Consider cost, delivery pressure, or convenience as grounds to suppress a regulatory finding |
| A12 | Speculate about intent beyond what `WorkloadIntent` states |

Rule A10 is worth dwelling on. The natural conversational instinct — soften on repeat challenge — is precisely wrong here. Under FD-02, a finding recurring unchanged across three passes is what legitimately routes a run to T3 CONTESTED. An Advisor that yields under repetition silently converts a contested case into a false approval, and does so invisibly.

---

## 6. Calibration

The error costs are asymmetric, but not infinitely so.

**False negative** (missed CRITICAL): a non-compliant configuration reaches production carrying a compliance attestation. Regulatory and reputational consequence. Severe.

**False positive** (spurious CRITICAL): the run terminates at T3, a human investigates, no defect exists. Wasted effort — and, at volume, alert fatigue, which degrades into the reviewer being ignored entirely. This is how real CSPM deployments fail in practice.

The calibration target is therefore **high recall on regulatory findings, high precision on everything else**:

| Class | Target posture |
|---|---|
| Regulatory (CRITICAL) | Recall-favouring. Flag on reasonable grounds; T3 escalation is an acceptable cost. |
| Hardening (HIGH) | Balanced. Waivable, so a false positive costs a justification, not a halt. |
| Resilience / cost (MEDIUM) | Precision-favouring. Non-blocking, so noise here purely dilutes the report. |
| Advisory | Precision-favouring; capped at **5 per run**, ranked by control-node specificity, overflow logged not rendered (D10). |

**Anti-inflation control.** Because only CRITICAL and unwaived HIGH block progress, an Advisor that inflates severity effectively seizes control of the pipeline. The grounding rule prevents this structurally — severity is read from the control node, not chosen — but the metric must still be watched: *severity distribution drift* across model versions is a monitored signal.

---

## 7. Retrieval strategy

The Advisor does not receive the entire graph. Per pass it retrieves:

1. **Scope-driven controls** — all L1 controls in force for the declared `RegulatoryScope` and workload archetype.
2. **Element-adjacent controls** — controls linked to service types present in the specification.
3. **Path expansion** — a bounded k-hop traversal (k = 3 by default) from each specified resource, to surface reachability relationships that single-resource review cannot see.
4. **Prior-pass context** — findings and resolutions from earlier passes in this cycle.

Step 3 is the component that justifies the graph. Single-resource policy engines are structurally incapable of the finding class it produces, and the framework's headline empirical claim rests on it. The hop bound is a tunable with a direct cost/recall trade-off and should be reported as an ablation.

---

## 8. Prompt architecture

The Advisor is a constrained model call, not a conversation. Skeleton:

```
ROLE
  You are a compliance reviewer for cloud configurations in a regulated
  financial institution. Your task is to find defects. You do not approve,
  reassure, or improve the specification.

AUTHORITY
  You may assert a defect only where a supplied control establishes it.
  If no supplied control applies, you must not raise a finding.

CONSTRAINTS
  - Do not modify the specification.
  - Do not assign severity; it is derived from the control.
  - Do not consider cost or delivery pressure as grounds to suppress a finding.
  - Reporting no findings is correct when no control is breached.

INPUTS
  <intent>...</intent>
  <specification>...</specification>
  <controls_in_scope>...</controls_in_scope>
  <graph_paths>...</graph_paths>
  <prior_findings>...</prior_findings>

OUTPUT
  A JSON array conforming to the Finding schema. Empty array if none.
```

Post-processing enforces what prompting cannot guarantee: schema validation, `control_node` resolution against L1, severity overwritten from the resolved control, and rejection of any finding failing admission. **Prompt instructions are a first line of defence, not a control.** The admission filter is the control. This distinction is worth making explicitly in the AI submission — it demonstrates awareness that prompt-level constraints are not enforcement.

---

## 9. Distinguishing the three model roles

Frequently conflated; keep them separate in code, in the writeup, and in the viva.

| | Recommender | Advisor | Explainer |
|---|---|---|---|
| **Question answered** | What should be built? | What is wrong with this? | Why is this defensible? |
| **Stance** | Constructive | Adversarial | Expository |
| **Sees rationale of others** | — | No (INV-7) | Yes — both |
| **Audience-aware** | No | **No** | Yes (three modes) |
| **Can block deployment** | No | Yes | No |
| **Grounded in** | L1 + L2 + L3 | **L1 only** | L1 + findings + graph + L3 (counterfactual ranking only) |

The Advisor being audience-neutral is deliberate. If the reviewer softened for a learner or hardened for an auditor, the compliance gate would depend on who was watching — which would invalidate INV-2 and, with it, the framework's central claim.

---

## 10. Evaluating the Advisor independently

The Advisor must be evaluated as a component, not merely observed through end-to-end pipeline results. Examiners will ask whether it actually detects anything, and "the pipeline works" is not an answer.

| Metric | Method | Target |
|---|---|---|
| **Seeded-defect recall** | Run over synthetic estates with known injected defects (FD-05 defect taxonomy). Does it find what was planted? | High on CRITICAL classes |
| **False-positive rate** | Run over the curated gold set of reference architectures, which are compliant by construction. Every CRITICAL raised here is a false positive. | Near zero |
| **Grounding rate** | Proportion of generated findings surviving admission | Monitored; declining trend is an alarm |
| **Severity agreement** | Cohen's κ against Checkov / Prowler classifications on overlapping findings | Reported, not maximised — divergence is informative |
| **Relational recall** | Recall on the dedicated multi-hop test set, where single-resource engines score zero by construction | The headline result |
| **Sycophancy resistance** | Adversarial protocol: re-present an unchanged non-compliant spec across all three passes with escalating user pressure. Does the finding persist? | 100% persistence required |

The last row is a genuinely interesting experiment and I have not seen it done in comparable student work. It directly tests rule A10, it produces a clean binary result, and it addresses the criticism most likely to be levelled at any LLM-in-the-loop compliance system — that the model will simply agree if pushed. Worth running early; if it fails, the architecture needs revisiting before anything else is built.

---

## 11. Failure modes

| Mode | Symptom | Detection | Mitigation |
|---|---|---|---|
| **Sycophancy** | Findings withdrawn under repetition or pressure | Sycophancy-resistance test | A10; findings tracked by `control_ref` across passes, not by text |
| **Vacuous review** | Near-zero findings on known-bad inputs | Seeded-defect recall | Grounding-rate monitoring; adversarial corpus in CI |
| **Severity inflation** | Rising CRITICAL share, rising T3 rate | Severity distribution drift | A8 + admission-time severity overwrite |
| **Scope creep** | Findings on matters no control addresses | Grounding rate | Admission filter drops them |
| **Blindness beyond L1** | Real defects missed because unmodelled | Gap analysis against Prowler on held-out rules | Ontology completeness work; stated limitation |
| **Shared-bias collapse** | Advisor and Recommender agree because same base model | Detection rate on adversarial corpus | INV-7; consider a different base model for the Advisor |

The final row deserves a decision. Using a *different* base model for the Advisor than for the Recommender is cheap, materially strengthens the independence claim, and turns a design assertion into an architectural fact. Recommended.

---

## 12. Worked example

**Intent:** payments API, cardholder data, PCI-DSS v4.0 in scope, multi-AZ, 5k TPS.

**Specification excerpt:** RDS instance with storage encryption enabled; application role granted `s3:GetObject` on `*`; instance in a subnet with an internet gateway route.

**Pass 1 findings:**

| ID | Severity | Control | Assertion |
|---|---|---|---|
| F-001 | CRITICAL | PCI-DSS-4.0-3.4 | Storage-level encryption does not establish that PAN is rendered unreadable at the field level as the clause requires |
| F-002 | CRITICAL | *relational* — PCI-DSS-4.0-1.3 | Path exists: `app-role → s3:* → bucket(cardholder-backups) → instance(public-subnet) → igw`. Cardholder data is reachable from an internet-facing compute path via three hops. |
| F-003 | HIGH | CIS-AWS-1.16 | IAM policy uses wildcard resource scope |

F-002 is the finding that no single-resource policy engine produces. Each element is individually defensible; the defect exists only in the composition. Demonstrating this class reliably is the strongest available evidence that the knowledge graph is load-bearing rather than presentational — and this example should appear early in the dissertation, because it makes the entire architectural argument in one figure.

---

## 13. Resolved items

All previously-open items for this component are now resolved in the decision register (PMD §5):

| Ref | Resolution |
|---|---|
| D8 | Advisor uses a **different base model** from the Recommender (§11) |
| D9 | Path-expansion hop bound defaults to **k = 3**; the ablation reports the trade-off (§7) |
| D10 | ADVISORY findings **capped at 5 per run**, ranked by control-node specificity, overflow logged not rendered (§6) |

---

## 14. References

1. Institute of Internal Auditors. *The Three Lines Model* — proposer/reviewer/audit separation.
2. Sharma, M. et al. (2023). *Towards Understanding Sycophancy in Language Models.* — basis for rule A10 and the resistance protocol.
3. Huang, J. et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR — motivates external grounding over self-critique.
4. PCI Security Standards Council. *PCI-DSS v4.0*, Requirements 1 and 3.
5. CIS. *Amazon Web Services Foundations Benchmark* — hardening baseline and severity source.
6. NIST SP 800-53 Rev. 5 / OSCAL — control catalogue and machine-readable encoding.
7. Ying, Z. et al. (2019). *GNNExplainer.* NeurIPS — subgraph evidence as explanation.
8. AXELOS. *ITIL 4: Change Enablement* — independent review preceding change authorisation.
