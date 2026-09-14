# FD-07 — Ontology Specification

**Project:** Knowledge Graph-Based Cloud Configuration Recommendation Framework for Financial Enterprises using Explainable AI
**Document ID:** FD-07
**Status:** Baseline
**Governs:** The L1 (normative) layer of the knowledge graph, its encoding schema, and Phase 1 of the milestone plan
**Depends on:** FD-02 (severity derivation), FD-03 (provenance layering), FD-04 (grounding rule), FD-05 (scope, defect taxonomy)
**Resolves:** D12/D16 (OSCAL internal vs export) — export-only, see §9

---

## 1. Purpose

Every compliance claim the framework makes resolves, eventually, to a node in the normative layer. The Advisor's grounding rule (FD-04 §4) requires it; severity derivation (FD-02 §4) reads from it; the constraint mask (FD-05 §2) filters against it; the Explainer cites it (FD-06 §3). If the encoding of that layer is vague, every downstream guarantee is vague with it.

This document specifies **what an L1 node is, how a control is encoded, how a control connects to a checkable configuration predicate, and how severity is made derivable rather than asserted.** It is the controlling reference for Phase 1, which the PMD (§10) and FD-05 (§12) both name as the phase where projects of this shape stall.

It does **not** specify the observed (L2) or behavioural (L3) layers beyond the edges L1 predicates must traverse to evaluate. Those layers are authored by Agent 2 and the run recorder respectively (FD-01 §3, FD-03 §5); their provenance rules are in FD-03 §5 and are not restated here.

---

## 2. Design position: L1 is authored, not learned

The single most defensible property of this architecture is that its compliance logic is **curated from citable sources**, not inferred by a model (FD-05 §2). A regulator can be shown the clause a finding rests on; the finding is not the output of a statistical estimator whose behaviour on the next input is unknown.

This document must preserve that property at the schema level. Two rules follow and are non-negotiable:

- **No L1 node is created by a model.** L1 is hand-authored from primary sources (§3), reviewed against the gold set (§13), and version-pinned. A model may *read* L1; it may never *write* it.
- **Severity is a stored property of the control, not a computed or prompted value.** It is set at authoring time from the source framework's own classification (§6). This is what makes the blocking decision in FD-02 auditable.

---

## 3. Source layers

L1 draws on four source vocabularies, in decreasing order of enforcement authority. This is the "ontology layers" line in PMD §6, made concrete.

| Layer | Source | Role in L1 | Enforcement |
|---|---|---|---|
| **Topology** | AWS Config resource schema (`AWS::*::*` resource types and their properties) | Vocabulary of what a configuration *is* — service types and their configurable properties | Structural; the substrate predicates are written against |
| **Control** | PCI-DSS v4.0, CIS AWS Foundations Benchmark | The enforced obligations. Each becomes a `Control` node with a checkable predicate | **Enforced** (in-scope per D2) |
| **Cross-reference** | NIST SP 800-53 Rev. 5, encoded via OSCAL | Control-family vocabulary and OSCAL export identity; **not enforced** | Reference only |
| **Domain** | FIBO (Financial Industry Business Ontology) | Anchors data-classification nodes to formal financial concepts (§8) | Reference only; legitimacy, not enforcement |

Per D2 (FD-05 §3), only PCI-DSS v4.0 and CIS AWS Foundations are *enforced*. NIST/OSCAL is a cross-reference layer that supplies control-family vocabulary and the export identity without the encoding cost of a third enforced framework. FIBO is cited for domain legitimacy at low cost and enforces nothing.

---

## 4. Node and edge schema

L1 is a labelled property graph (Neo4j Community, PMD §6). Every node and edge carries a `provenance` property tagging it `L1` with a `source` (`pci-dss-v4`, `cis-aws-1.5`, `nist-800-53`, `aws-config`, `fibo`) and a `source_version`. This is the tag FD-03 §5 requires; L1 tags are immutable once frozen (§12).

### 4.1 Node labels

| Label | Represents | Key properties |
|---|---|---|
| `Framework` | An enforced or referenced standard | `id`, `title`, `version`, `enforced` (bool) |
| `Control` | A single obligation or hardening item | `id`, `clause_ref`, `title`, `obligation_summary`, `classification`, `severity`, `checkable` (bool) |
| `ConfigPredicate` | A machine-checkable assertion the control requires | `id`, `kind` (`property` \| `relational`), `expression`, `hop_bound` (relational only) |
| `ServiceType` | An AWS resource type | `id` (e.g. `AWS::RDS::DBInstance`), `service` |
| `ServiceProperty` | A configurable property of a service type | `id`, `name`, `value_domain` |
| `Constraint` | A hard constraint used by the S2 mask | `id`, `predicate_ref`, `hard` (always true for L1 constraints) |
| `DataClass` | A sensitivity class of data | `id` (e.g. `cardholder-data`, `pii`), `sensitivity` |
| `FIBOConcept` | A referenced financial-domain concept | `id`, `iri` |
| `ControlFamily` | A NIST 800-53 family, cross-reference | `id` (e.g. `SC`, `AC`), `title` |

### 4.2 Relationship types

| Type | From → To | Meaning |
|---|---|---|
| `GOVERNS` | `Framework → Control` | The framework defines this control |
| `REQUIRES` | `Control → ConfigPredicate` | Satisfying the control requires this predicate to hold |
| `EVALUATED_OVER` | `ConfigPredicate → ServiceProperty` \| `ServiceType` | The predicate reads these properties / types |
| `APPLIES_TO` | `Control → ServiceType` | The control is in force wherever this service type appears |
| `CONCERNS` | `Control → DataClass` | The control is triggered by the presence of this data class |
| `HAS_PROPERTY` | `ServiceType → ServiceProperty` | Topology: this type exposes this property |
| `ENFORCED_BY` | `Constraint → ConfigPredicate` | The S2 hard mask uses this predicate as a filter |
| `CROSS_REFERENCES` | `Control → ControlFamily` | NIST family mapping, for OSCAL export |
| `ALIGNS_WITH` | `DataClass → FIBOConcept` | Domain anchor (§8) |

### 4.3 The `kg://` URI scheme

Every L1 node is addressable by a stable URI. Findings cite these (FD-04 §3 `control_node`, `evidence_path`); the scheme must therefore be fixed and version-stable.

```
kg://framework/<framework-id>
kg://control/<framework-id>/<clause-ref>          e.g. kg://control/pci-dss-v4/3.4
kg://predicate/<predicate-id>
kg://service/<service-type>                        e.g. kg://service/aws-rds-dbinstance
kg://property/<service-type>/<property-name>
kg://constraint/<constraint-id>
kg://data/<data-class>                             e.g. kg://data/pan
kg://fibo/<concept-id>
```

L2 nodes (observed resources, edges) use `kg://resource/<id>` and `kg://edge/<type>`, consistent with the `evidence_path` examples in FD-04 §3. L1 predicates of `kind: relational` traverse those L2 edges at evaluation time (§7) but are themselves authored in L1.

---

## 5. Worked encoding — one control, end to end

The PCI-DSS 3.4 example threaded through FD-02 §6 and FD-04 §12, encoded:

```
(Framework  kg://framework/pci-dss-v4  {enforced: true})
   -[:GOVERNS]->
(Control     kg://control/pci-dss-v4/3.4
   { clause_ref: "3.4",
     title: "Render PAN unreadable anywhere it is stored",
     obligation_summary: "PAN must be rendered unreadable at rest by an approved method.",
     classification: "mandatory",
     severity: "CRITICAL",
     checkable: true })
   -[:CONCERNS]-> (DataClass kg://data/pan {sensitivity: "regulated"})
   -[:REQUIRES]->
(ConfigPredicate kg://predicate/pan-field-unreadable
   { kind: "property",
     expression: "for every store holding data:pan, a field-level unreadable-rendering method is applied",
     ... })
   -[:EVALUATED_OVER]-> (ServiceProperty kg://property/aws-rds-dbinstance/field-encryption)
(Control kg://control/pci-dss-v4/3.4) -[:CROSS_REFERENCES]-> (ControlFamily kg://... SC)
(DataClass kg://data/pan) -[:ALIGNS_WITH]-> (FIBOConcept kg://fibo/payment-card-number)
```

A finding raised against a spec resolves its `control_node` to `kg://control/pci-dss-v4/3.4`, reads `severity: CRITICAL` **off the node**, and attaches the `evidence_path` traversed to establish the breach. Nothing about the severity is decided by the Advisor — this is the mechanism behind FD-04 §4 and FD-02 §4.

---

## 6. Severity derivation

Severity is a property of the `Control` node, set at authoring time by this fixed rule:

| Source classification | `classification` | `severity` |
|---|---|---|
| Mandatory clause of an enforced regulation (PCI-DSS) | `mandatory` | **CRITICAL** |
| Hardening baseline without a direct regulatory mapping (CIS Level 1) | `hardening` | **HIGH** |
| Resilience / cost / operational heuristic | `heuristic` | **MEDIUM** |
| Informational / forward-looking | `informational` | **ADVISORY** |

This table is the authoritative source for the FD-02 §4 severity taxonomy; that document consumes it, this one defines it. Two consequences the writeup should state:

- A relational control (e.g. a reachable-exfiltration-path prohibition under PCI-DSS 1.3) is `mandatory` and therefore CRITICAL, even though the breach is established by a path rather than a single property. Severity attaches to the **control**, not to the detection mechanism.
- Because severity is stored, an examiner can audit the CRITICAL/HIGH assignment of every control without running the system. This is a property no LLM-assigned severity offers, and it is worth foregrounding.

---

## 7. Control-to-configuration crosswalk

The crosswalk — `Control -[:REQUIRES]-> ConfigPredicate -[:EVALUATED_OVER]-> ServiceProperty` — is the load-bearing content of L1 and the bulk of the Phase 1 effort. A `ConfigPredicate` has two kinds:

**`property` predicates** assert a condition over the values of one or more service properties of a single resource (e.g. `StorageEncrypted = true`, `PubliclyAccessible = false`). These are what open policy engines already check, and encoding them is mechanical; the CIS Benchmark and the Checkov/Prowler rule sets are direct references for the mapping.

**`relational` predicates** assert the *absence or presence of a path* through the graph, bounded by `hop_bound` (default k = 3, the tunable of D9). Example: PCI-DSS 1.3 requires that no path exists from a `data:pan` store to an internet-egress node within k hops. This predicate is evaluated against L2 topology (observed estate) or the candidate's dependency graph (FD-01 S4) at review time. Relational predicates are the encoding root of the DF-7 defect class (FD-05 §5) and the headline C1 claim — they are exactly what single-resource engines cannot express.

The retrieval strategy in FD-04 §7 is served directly by this schema:

1. **Scope-driven** — `MATCH (f:Framework {enforced:true})-[:GOVERNS]->(c:Control)` filtered by `RegulatoryScope` and archetype.
2. **Element-adjacent** — `MATCH (c:Control)-[:APPLIES_TO]->(t:ServiceType)` for every service type present in the spec.
3. **Path expansion** — traverse L2/dependency edges to `hop_bound` from each specified resource, then match relational predicates whose paths the traversal realises.

---

## 8. FIBO domain layer

FIBO enforces nothing. Its role is to anchor each `DataClass` node to a formal financial concept via `ALIGNS_WITH`, so that "cardholder data" and "PII" are not free-text strings but references into an accepted domain ontology. `cardholder-data → fibo:payment-card-number`, `pii → fibo:party-identity`, and similar.

The benefit is proportionate to the cost: a handful of `ALIGNS_WITH` edges buys a citable domain grounding that reads as academic rigour in the AI submission (PMD §6), at essentially zero encoding effort. Do not over-invest here — the enforcement value is nil, and the legitimacy value saturates after a few well-chosen alignments.

---

## 9. OSCAL — export-only (resolves D12/D16)

**Decision: OSCAL is an import source for control identity and an export format for results. It is not the internal graph encoding.**

- **Import.** Where an OSCAL catalog exists for a source (NIST 800-53), its control IDs and family structure seed the `Control` and `ControlFamily` nodes and their `CROSS_REFERENCES` edges. This gives every control a stable OSCAL identity for export.
- **Internal.** The live query substrate is the property graph of §4. OSCAL's document model is a poor fit for the multi-hop reachability queries the framework depends on (§7); forcing the graph into OSCAL's structure would triple the Phase 1 effort (FD-05 §12 warns Phase 1 is the stall point) for no query benefit.
- **Export.** Run results are emitted as OSCAL `assessment-results` at the boundary, per FD-06 §10, so the output plugs into existing GRC tooling.

**Rationale for the writeup.** Storing the authoring substrate natively while importing/exporting OSCAL gives the interoperability argument (FD-06 §10) without paying the encoding tax, and keeps the reachability queries (the project's whole point) fast. Revisit only if a future enforced framework ships primarily as an OSCAL catalog with no simpler source. This closes both D12 (FD-05) and its duplicate D16 (FD-06).

---

## 10. Immutability and versioning

L1 is **frozen and version-pinned** once encoded for a milestone. Per FD-03 §7, every run is reproducible from `(spec_hash, graph_version, model_version)`; `graph_version` pins the L1 encoding. A control re-classification or added predicate produces a **new** `graph_version`, never an in-place edit of a frozen one — mutable normative content is unusable as audit evidence, the same argument FD-03 §4 makes for run records.

Feedback never writes L1 (FD-03 §5). The provenance tag on every L1 node is the structural guarantee: the enrichment pipeline is forbidden from touching nodes tagged `L1`, and this is enforced at write time, not by convention.

---

## 11. Coverage and the honest limitation

Per FD-04 §4, **coverage of the framework is exactly coverage of L1.** The Advisor cannot flag a defect for which no control is encoded. This is a real limitation and belongs in the threats-to-validity section, not buried.

Two consequences for scope:

- Encode PCI-DSS v4.0 and CIS AWS Foundations **for the three archetypes only** (D2). Do not attempt whole-framework coverage; encode the controls the three archetypes actually exercise, and state the scoped claim (FD-05 §11).
- Report an explicit **coverage manifest**: which clauses of each framework are encoded, which are out of scope, and which are known gaps. A named gap reads as rigour; an unnamed one reads as an oversight a reviewer found first.

---

## 12. Validation against the gold set

L1 is not trusted on authoring alone. The gold set (FD-05 §4C, Phase 2) is the first consumer that validates it: every gold configuration is compliant by construction, so **any CRITICAL the encoded L1 raises against the gold set is either a false positive or an L1 encoding error** (FD-04 §10). Running the freshly-encoded L1 against the gold set is the Phase 1→2 acceptance test.

Additionally, the expert-review protocol (D13, FD-05 §11) reviews the control-to-predicate crosswalk directly: practitioners confirm that each `ConfigPredicate` faithfully represents its clause. This converts the crosswalk from author-asserted to expert-checked at low cost and is the single highest-leverage validation of L1.

---

## 13. Build sequence (Phase 1)

Dependency-ordered. This is the expansion of FD-05 §12 step 2.

1. Encode `Framework`, `ControlFamily`, and the AWS Config `ServiceType`/`ServiceProperty` topology for the in-scope service types.
2. Author `Control` nodes for the in-scope PCI-DSS and CIS clauses, with `classification` and `severity` set from §6.
3. Write `property` `ConfigPredicate`s and their `EVALUATED_OVER` edges — mechanical, cross-check against Checkov/CIS.
4. Write `relational` `ConfigPredicate`s for the DF-7 defect class, with `hop_bound` — the load-bearing, low-volume, high-value predicates.
5. Attach `DataClass` and `ALIGNS_WITH` FIBO edges.
6. Seed OSCAL identities and `CROSS_REFERENCES` (§9 import).
7. Freeze `graph_version`; run against the gold set (§12); publish the coverage manifest (§11).

Steps 3–4 are the bulk of the work and the most error-prone. Timebox them; reduce control *count* before reducing encoding *quality*, per the PMD risk register.

---

## 14. Open items

| Ref | Item |
|---|---|
| D9 | Default hop bound `k` for relational predicates — shared with FD-04 §7; resolve by ablation |
| — | Whether CIS Level 2 items are encoded at all, or only Level 1 (Level 1 only is the lazy default; expand only if an archetype needs it) |
| — | Granularity of `DataClass` — three classes (`cardholder-data`, `pii`, `low-sensitivity`) is the proposed minimum matching the three archetypes |

---

## 15. References

1. PCI Security Standards Council. *PCI-DSS v4.0* — enforced control source.
2. CIS. *Amazon Web Services Foundations Benchmark* — hardening baseline and severity source.
3. NIST. *SP 800-53 Rev. 5* and *OSCAL* (catalog, profile, assessment-results models) — cross-reference layer and export identity.
4. AWS. *AWS Config Resource Schema* / *CloudFormation Resource Specification* — topology vocabulary.
5. EDM Council. *Financial Industry Business Ontology (FIBO)* — domain anchor.
6. Bridgecrew. *Checkov*; Aqua Security. *tfsec*; Prowler Team. *Prowler* — reference mappings for `property` predicates.
7. Neo4j. *Property Graph Model* — internal encoding substrate.
