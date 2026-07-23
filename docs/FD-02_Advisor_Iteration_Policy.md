# FD-02 — Advisor Iteration Policy

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-02
**Status:** Baseline
**Governs:** Stage S3 of FD-01
**Depends on:** FD-01 (Unified Flow), FD-03 (Feedback Loop)

---

## 1. Purpose

Stage S3 places the candidate specification under adversarial review. This document defines when that review stops, what it is permitted to let through, and what happens when it cannot reach agreement.

An unbounded critique loop is not a minor implementation detail. It is the difference between a system that terminates predictably under audit and one that does not.

---

## 2. Problem statement

The original flowcharts specified a single corrective pass: advisor rejects → suggestions implemented → proceed. This is unsafe, because the patch is never re-examined. A fix for a CRITICAL finding can introduce a second CRITICAL finding and reach deployment unchallenged.

The obvious remedy — loop until the advisor is satisfied — is worse. It admits three failure modes:

1. **Non-termination.** Advisor and generator disagree indefinitely.
2. **Oscillation.** The spec alternates between two states, each of which the advisor objects to on different grounds.
3. **Degradation.** Extended self-correction drifts away from a correct answer rather than toward one. This is well documented: without an external source of truth, iterative self-critique reliably degrades outputs in later rounds, and models frequently revise correct answers into incorrect ones under critique pressure.

The policy below is designed to admit useful correction while structurally excluding all three.

---

## 3. Evidence base for the cap

The number **3** is not arbitrary. Four independent lines of evidence converge on the same region.

| Source | Finding | Implication |
|---|---|---|
| Iterative self-refinement literature (Self-Refine, Reflexion) | Gains from feedback-and-revise loops concentrate in the first one to two rounds and flatten thereafter | Marginal value of pass 4+ is near zero |
| Self-correction critiques (Huang et al., ICLR 2024) | Without external grounding, later self-correction rounds degrade accuracy | Additional passes carry *negative* expected value beyond a small bound |
| ITIL / financial-sector change advisory board practice | Normal changes receive one to two review rounds, then escalate to a named human authority | Industry precedent for bounded review with mandatory escalation |
| Fixed-point iteration in compilers and constraint solvers | Bounded passes with an explicit convergence test, never "until satisfied" | Established engineering pattern for guaranteed termination |

**Important qualification for the writeup.** The self-refinement literature concerns *self*-critique, where the critic and generator are the same model. Our Advisor is grounded in the knowledge graph and separated from the Recommender (INV-7), so it is closer to external verification than to self-critique — which is exactly why bounded iteration is defensible here at all. State this distinction explicitly; it is the reason the design is not subject to the degradation result in its strongest form.

**Cap: 3 passes.** One pass to surface findings, one to verify the correction, one margin for a correction that legitimately reveals a second-order issue. Beyond that, disagreement is substantive rather than mechanical and belongs with a human.

---

## 4. Severity taxonomy

Every finding carries exactly one severity. Severity determines loop behaviour, so the taxonomy must be crisp and rule-derivable, not a judgement call made per run.

| Severity | Definition | Loop behaviour |
|---|---|---|
| **CRITICAL** | Violates a mandatory regulatory control in scope for the declared intent (e.g. unencrypted cardholder data under PCI-DSS Req. 3), or creates a reachable data-exfiltration path | **Blocks.** Must reach zero before S4. |
| **HIGH** | Violates a hardening baseline (CIS Level 1) without a direct regulatory mapping, or creates a single point of failure against a declared availability target | Blocks unless explicitly waived by the user with a recorded justification |
| **MEDIUM** | Suboptimal against cost, operational, or resilience heuristics | Does not block. Carried into the explanation bundle. |
| **ADVISORY** | Stylistic, informational, or forward-looking | Does not block. Logged. |

**Severity is assigned by the control's own classification in the knowledge graph, not by the model.** If the graph links the finding to a mandatory clause of an in-scope regulation, it is CRITICAL by construction. This keeps the blocking decision auditable and reproducible — a property an examiner will probe, and a property no LLM-assigned severity can offer.

---

## 5. The policy

### 5.1 Rules

| ID | Rule |
|---|---|
| **P1 — Cap** | At most 3 advisor passes per acceptance cycle. |
| **P2 — Early exit** | Zero CRITICAL and zero HIGH findings → exit immediately to S4. Most runs should terminate here on pass 1. |
| **P3 — Fixed point** | A canonical hash of the spec is recorded each pass. If a hash repeats, halt: the loop is oscillating and further passes cannot help. |
| **P4 — Severity gate** | CRITICAL blocks unconditionally. HIGH blocks unless waived with recorded justification. MEDIUM and ADVISORY never block. |
| **P5 — Monotonicity check** | If the CRITICAL count increases between passes, halt immediately. The corrective process is making things worse, and continuing is unjustifiable. |
| **P6 — Non-convergence** | Cap reached with unresolved CRITICAL findings → terminate at **T3 CONTESTED** with a Contested Findings Report. Never silently pass a CRITICAL finding. |
| **P7 — Counter reset** | The user acceptance gate (S8) resets the pass counter. A user-edited spec begins a fresh review cycle, itself capped at 3. |

### 5.2 Rule P7 and the global bound

P7 creates the only route to more than three total passes. This is intentional: a human has intervened, and human judgement is the external grounding the loop otherwise lacks. Nonetheless the *global* number of acceptance cycles must also be bounded — a `--max-cycles` parameter defaulting to 5 — or a user pressing enter repeatedly could drive unbounded compute. Cycle exhaustion terminates at T4 ABORTED.

### 5.3 State machine

```
        ┌──────────────────────────────────────────┐
        │                                          │
        ▼                                          │
   [PASS n ≤ 3] ──── zero CRIT/HIGH ────────────▶ CONVERGED → S4
        │                                          │
        ├── hash repeat (P3) ──────────────────▶ OSCILLATING → T3
        │                                          │
        ├── CRIT count ↑ (P5) ─────────────────▶ DIVERGING → T3
        │                                          │
        ├── findings remain, n < 3 ─── patch ──────┘
        │
        └── findings remain, n = 3 ────────────▶ NON-CONVERGENT → T3
```

### 5.4 Reference implementation

Here `advisor` is the Advisor (FD-04) and `generator` is the Recommender operating in patch mode — the patcher, per the FD-01 §3 patcher note. It is not a separate actor.

```python
MAX_PASSES = 3

def advisor_loop(spec, intent, kg):
    seen_hashes = {canonical_hash(spec)}
    prev_critical = None
    trace = []

    for n in range(1, MAX_PASSES + 1):
        findings = advisor.review(spec, intent, kg)   # no recommender rationale passed (INV-7)
        crit = [f for f in findings if f.severity == "CRITICAL"]
        high = [f for f in findings if f.severity == "HIGH" and not f.waived]
        trace.append(Pass(n, findings, canonical_hash(spec)))

        if not crit and not high:                     # P2
            return Converged(spec, trace)

        if prev_critical is not None and len(crit) > prev_critical:   # P5
            return Contested(spec, trace, reason="DIVERGING")
        prev_critical = len(crit)

        if n == MAX_PASSES:                           # P6
            return Contested(spec, trace, reason="NON_CONVERGENT")

        spec = generator.patch(spec, findings)
        h = canonical_hash(spec)
        if h in seen_hashes:                          # P3
            return Contested(spec, trace, reason="OSCILLATING")
        seen_hashes.add(h)

    raise AssertionError("unreachable")
```

### 5.5 Termination argument

The loop halts in all cases. Every iteration either returns, or increments `n` toward the bound `MAX_PASSES`; the branch at `n == MAX_PASSES` returns unconditionally before any further patch is attempted. The hash set and monotonicity checks are additional *early* exits and cannot extend execution. Therefore the loop performs at most 3 advisor invocations and terminates. Combined with the `--max-cycles` bound on P7, total system passes are bounded by `3 × max_cycles`.

A short termination argument of this kind is cheap to include and disproportionately improves how a systems examiner reads the design.

---

## 6. Contested Findings Report (T3)

Emitted when the loop halts with unresolved CRITICAL findings. This is a first-class output, not an error dump.

```json
{
  "run_id": "...",
  "terminal_state": "CONTESTED",
  "halt_reason": "NON_CONVERGENT | OSCILLATING | DIVERGING",
  "passes_executed": 3,
  "intent": { "...": "WorkloadIntent, with reconstruction confidence if review mode" },
  "unresolved_findings": [
    {
      "finding_id": "F-014",
      "severity": "CRITICAL",
      "control_ref": "PCI-DSS-3.4",
      "control_source": "kg://control/pci-dss-v4/3.4",
      "advisor_position": "Field-level encryption absent on the PAN column; clause requires rendering PAN unreadable at rest.",
      "generator_position": "Volume-level encryption applied; asserted as satisfying the clause.",
      "contested_point": "Whether volume-level encryption satisfies a clause specifying rendering PAN unreadable.",
      "evidence_subgraph": "...",
      "first_raised_pass": 1
    }
  ],
  "resolved_findings": [ "..." ],
  "spec_hash_trace": ["a3f...", "b71...", "a3f..."],
  "escalation": "HUMAN_REVIEW_REQUIRED"
}
```

The `contested_point` field is the one that matters. Stating precisely *where* two grounded reasoners disagree, and citing the clause under dispute, is more useful to a compliance officer than a confident recommendation would be — and it is honest about the limits of automated interpretation of regulatory text. Regulatory clauses genuinely are ambiguous; a framework that surfaces the ambiguity instead of resolving it silently is the more defensible design, and worth arguing as such.

---

## 7. Waiver handling

HIGH findings may be waived at S8. A waiver records: finding ID, waiving user, timestamp, free-text justification, and expiry. Waivers are written to the graph as first-class nodes linked to the finding and the deployed configuration.

Two consequences worth noting:
- Waived findings reappear on subsequent reviews of the same estate unless the waiver is still valid — the system does not forget an accepted risk, it tracks it.
- Accumulated waivers become a queryable risk register. This is a plausible commercial feature and costs almost nothing to build once the graph exists.

CRITICAL findings cannot be waived through the CLI under any flag. If the framework permits a mandatory regulatory control to be bypassed by a command-line argument, its compliance claim is void.

---

## 8. Instrumentation

Metrics to record per run (consumed by FD-03, and directly reportable as evaluation results):

| Metric | Purpose |
|---|---|
| Passes to convergence (distribution) | Validates the cap empirically. If the mode is 1 and the tail is thin, the cap is correct. If many runs hit 3, either the recommender or the advisor is miscalibrated. |
| Early-exit rate (P2) | Health of the recommender — high is good. |
| Oscillation rate (P3) | Ambiguity in the control encoding, or an unstable patcher. |
| Divergence rate (P5) | Patcher quality. Should be near zero. |
| Contested rate (P6) | Expected non-zero; a floor of genuinely ambiguous regulatory cases exists. |
| Findings resolved per pass, by severity | Whether the patch step is effective or merely churning. |
| Mean advisor latency and token cost per pass | Practical cost of the loop; feeds the cost/benefit argument for the cap. |

**Evaluation hook.** Report the passes-to-convergence distribution as a result in its own right, and include an ablation with the cap raised to 5 or 10 to demonstrate empirically that additional passes add nothing. That converts a design decision into a measured finding — a strong, low-cost addition to the AI submission.

---

## 9. Threats and mitigations

| Threat | Mitigation |
|---|---|
| Advisor and Recommender share biases from a common base model, so review is vacuous | INV-7 (no rationale sharing); Advisor grounded in KG rules rather than free generation; measure finding rate against a corpus of known-bad configurations to prove the Advisor actually detects |
| Cap of 3 hides a class of problems solvable in 4–5 | Ablation study (§8); report the tail |
| Severity misassignment lets a CRITICAL pass as MEDIUM | Severity derived from the control's classification in the graph, never model-assigned |
| Canonical hashing is unstable (key order, whitespace) so P3 never fires | Hash over a normalised, sorted, semantically canonical form; unit-test that a semantically identical spec hashes identically |
| Patcher makes cosmetic edits to escape the hash check without addressing the finding | Track *findings* across passes, not just spec hashes; a finding recurring with identical `control_ref` across all three passes is itself an oscillation signal |

The last row is a real adversarial hole in a naive implementation and is worth mentioning in the writeup as a demonstrated defence.

---

## 10. References

1. Madaan, A. et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback.* NeurIPS.
2. Shinn, N. et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* NeurIPS.
3. Huang, J. et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR.
4. Kim, G. et al. (2023). *Language Models can Solve Computer Tasks.* NeurIPS — bounded critic–actor loops.
5. AXELOS. *ITIL 4: Change Enablement* — change advisory board review rounds and escalation.
6. Aho, A., Lam, M., Sethi, R., Ullman, J. *Compilers: Principles, Techniques and Tools* — bounded fixed-point iteration.
7. PCI Security Standards Council. *PCI-DSS v4.0*, Requirement 3 — worked example of a mandatory control.
8. NIST SP 800-53 Rev. 5 — control classification source for severity derivation.
