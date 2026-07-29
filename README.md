# KGCR — Knowledge Graph-Based Cloud Configuration Recommendation

Recommend a concrete AWS configuration from a workload stated in business terms, and justify every choice as a traceable subgraph linking it to a regulatory clause and a cost or risk consequence. Then run the same machinery in reverse on an existing estate, by first reconstructing the intent it was built to serve.

One-line framing: an experienced cloud architect who has read every compliance standard, never forgets one, and writes down their reasoning every single time.

> **BCSE355L Cloud Architecture Design Project — Phase-I submission.**
> Course instructor: Dr. Priya V. Team: Udit (lead), Manya, Tanmoy.
> Start with the [Project Report](docs/Project_Report.md); [CLAUDE.md](CLAUDE.md) is the governing
> document for how this repository is worked in.

## Phase-I deliverables

| Deliverable | File |
|---|---|
| Project report — abstract, AWS services plan, progress, contribution matrix | [docs/Project_Report.md](docs/Project_Report.md) |
| Literature survey — 15 papers, 2023–2026, DOI-verified | [docs/Literature_Survey.md](docs/Literature_Survey.md) |
| Research gap analysis — Udit, papers 1–5 | [docs/Research_Gap_Udit.md](docs/Research_Gap_Udit.md) |
| Objectives — six, each with a measure | [docs/Objectives.md](docs/Objectives.md) |
| Novelty summary | [docs/Novelty.md](docs/Novelty.md) |
| Diagram 1 — AWS Cloud Architecture | [architecture/AWS_Architecture.png](architecture/AWS_Architecture.png) |
| Diagram 2 — Complete System Architecture | [architecture/System_Architecture.png](architecture/System_Architecture.png) |
| Dataset details | [dataset/dataset_description.md](dataset/dataset_description.md) |

Each is also generated as `.docx` for submission (`python docs/make_docx.py`); the Markdown is the
source of truth.

**Implementation status.** The reproducibility spine, the intent-first corpus generator, the defect
taxonomy with its relational (DF-7) test set, the Checkov labelling slice, and intent reconstruction
with per-field calibration are built and tested (130 tests, CI on Python 3.11 and 3.12). The
ontology encoding, recommender, Advisor and Explainer are not yet built, and the AWS environment
Terraform is authored but not applied. The `docs/` FD set remains the controlling specification.

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

## Development

Phase 0 scaffolding (FD-08). Requires Python 3.11+.

```bash
pip install -e ".[dev]"     # install with dev tooling (pinned versions)
PYTHONHASHSEED=0 pytest     # run the test suite
ruff check . && mypy        # lint and type-check
kgcr repro-info             # print the seed + version fingerprint for this env
kgcr corpus --count 500     # [dev] generate Corpus A and parse it into the graph
```

The tree follows the BCSE355L Phase-I guidelines (`docs/`, `architecture/`,
`dataset/`, `src/{frontend,backend,ml_model,aws}`, `results/`, `presentation/`);
[CLAUDE.md](CLAUDE.md) is the governing document.

- `src/backend/kgcr/` — the package. Today it provides the reproducibility spine
  (`repro`, `hashing`, `runrecord`, `versions`) that keys every result to
  `(spec_hash, graph_version, model_version)`, plus the `kgcr` CLI whose
  subcommands mirror the [planned interface](#planned-interface) (declared now,
  implemented by the phases that own them).
- `src/ml_model/` — entry points for the P8 intent reconstructor:
  `preprocessing.py` (generate the corpus into `dataset/processed/`), `train.py`
  (fit, write `model.pkl` and the evaluation report), `predict.py` (reconstruct
  one estate's intent with per-field confidence). Thin wrappers over
  `kgcr.reconstruction`; the library is where the logic and its tests live.
- `src/frontend/` — Phase-II scope; the Phase-I interface is the CLI.
- `src/backend/kgcr/corpus/` — Phase 3 (FD-05 §4A): the **intent-first** synthetic estate
  generator. An intent is sampled first (`intent`, `sampler`), an estate is
  rendered from it (`generator`, `estate`) carrying that intent as ground truth,
  and it is parsed into a dependency graph either directly (`graph`) or from a
  real `terraform show -json` plan (`plan_parser`). `splits` enforces
  estate-level, seed-family train/test separation (FD-05 §9); `pipeline` runs
  the whole thing. The corpus is clean at this phase — defect injection is
  Phase 5. No `terraform`/AWS is required to generate it.
- `environment/` — the FD-08 §8 bootstrap Terraform: day-one budget alarms and
  the cross-account read/write role split. Authored, not yet applied.
- `.github/workflows/ci.yml` — ruff, mypy, and pytest on every push.

## Context

This is an academic project spanning cloud architecture and applied AI. It is trained and evaluated on a synthetic, mined, and adversarial corpus; no real financial-sector data is used, and that limitation is stated openly in FD-05. The commercial analysis in PMD §12 is candid about what a student build can and cannot substantiate.

## License

Not yet specified.
