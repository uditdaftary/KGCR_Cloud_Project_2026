# KGCR — Knowledge Graph-Based Cloud Configuration Recommendation

Recommend a concrete AWS configuration from a workload stated in business terms, and justify every choice as a traceable subgraph linking it to a regulatory clause and a cost or risk consequence. Then run the same machinery in reverse on an existing estate, by first reconstructing the intent it was built to serve.

One-line framing: an experienced cloud architect who has read every compliance standard, never forgets one, and writes down their reasoning every single time.

> **Status: design specification (baseline).** This repository currently holds the foundation documents only. No code has been written yet; the `docs/` set is the controlling reference the implementation will follow.

## The gap this fills

Existing tools each cover one edge of the problem and none cover the middle:

- **CSPM** (Wiz, Prisma Cloud, Orca) detects violations in what already exists. No design-time recommendation.
- **Policy-as-code** (Checkov, tfsec, Prowler, OPA) checks one resource at a time. No recommendation, no justification beyond rule text, and by construction it cannot see multi-hop defects.
- **FinOps** (CloudHealth, Cloudability) finds waste but is compliance-blind.

The unoccupied intersection is design-time recommendation, compliance grounding, cost joint-optimisation, and audit-grade explanation, over a single graph representation. That intersection is this project.

## Core claims

| | Claim |
|---|---|
| **C1** | A graph representation detects multi-hop compliance violations that single-resource policy engines cannot reach by construction. |
| **C2** | Configuration review reframed as design with reconstructed intent: a review is a design whose intent was recovered rather than supplied. |
| **C3** | Explanation is the reasoning path itself, extracted from the graph, not prose narrated after the fact. Because the compliance logic is curated, most explanations are exact rather than approximate. |
| **C4** | Explanation is audience-relative in form but invariant in content. What the system concludes never changes with who is reading. |
| **C5** | Bounded adversarial review that reports irresolvable disagreement rather than manufacturing agreement. |

## Documents

Start with the [PMD](docs/PMD.md); it binds the rest. The FD documents specify individual subsystems.

| ID | Document | Covers |
|---|---|---|
| PMD | [Project Master Document](docs/PMD.md) | Thesis, scope, decision register, milestones, risk, commercial analysis |
| FD-01 | [Unified Flow Specification](docs/FD-01_Unified_Flow_Specification.md) | The single pipeline, its stages, terminal states, invariants, CLI |
| FD-02 | [Advisor Iteration Policy](docs/FD-02_Advisor_Iteration_Policy.md) | Bounded review loop, severity taxonomy, contested findings |
| FD-03 | [Feedback Loop Specification](docs/FD-03_Feedback_Loop_Specification.md) | Run records, L1/L2/L3 layering, learning uses, feedback pathologies |
| FD-04 | [Advisor Persona Specification](docs/FD-04_Advisor_Persona_Specification.md) | Reviewer role, the grounding rule, calibration, independent evaluation |
| FD-05 | [Data Strategy and Corpus Construction](docs/FD-05_Data_Strategy_and_Corpus_Construction.md) | Corpus sources, defect taxonomy, weak supervision, circularity defences |
| FD-06 | [Explainer Specification](docs/FD-06_Explainer_Specification.md) | Subgraph extraction, counterfactuals, audience modes, XAI evaluation |
| FD-07 | [Ontology Specification](docs/FD-07_Ontology_Specification.md) | L1 node/edge schema, control-to-config crosswalk, severity derivation, FIBO/OSCAL |
| FD-08 | [Environment Build](docs/FD-08_Environment_Build.md) | Three-account topology, cross-account IAM, cost controls, Phase 0 exit |

## Scope

Deliberately narrow, to demonstrate depth rather than breadth:

- **Three workload archetypes:** payments API (cardholder data), customer data platform (PII), internal reporting service (cost-dominant contrast case).
- **Two enforced frameworks:** PCI-DSS v4.0 and CIS AWS Foundations Benchmark. NIST 800-53 / OSCAL is a cross-reference and export layer; FIBO anchors the financial domain.

## Planned interface

```
kgcr design  --intent "<statement>" [--audience=<a>] [--plan-only] [--budget=<n>]
kgcr review  --account <id> [--audience=<a>] [--attest-only]
kgcr explain --run <run-id> [--audience=<a>]
kgcr plan    --spec <spec-id>
kgcr apply   --plan <plan-id>
kgcr history [--account <id>]
```

`--audience` (`architect` / `auditor` / `learner`) changes only how a result is rendered. The underlying reasoning and conclusions are identical across renderings; this invariant is tested, not asserted.

## Roadmap

The milestone plan (PMD §10) is dependency-ordered and phase-based. The near-term critical path:

1. **Phase 0 — environment** (FD-08): three accounts wired, budget alarms live, cross-account read working.
2. **Phase 1 — ontology** (FD-07): encode the L1 controls for PCI-DSS and CIS across the three archetypes. This is the foundation every compliance claim rests on, and the phase most likely to be underestimated.
3. **Phase 2 — gold set** (FD-05 §4C): 50 to 100 hand-verified reference configurations that validate the L1 encoding.

Later phases build the generator, labelling pipeline, Advisor, Recommender, intent reconstructor, and Explainer, then the evaluation suite and human study.

## Context

This is an academic project spanning cloud architecture and applied AI. It is trained and evaluated on a synthetic, mined, and adversarial corpus; no real financial-sector data is used, and that limitation is stated openly in FD-05. The commercial analysis in PMD §12 is candid about what a student build can and cannot substantiate.

## License

Not yet specified.
