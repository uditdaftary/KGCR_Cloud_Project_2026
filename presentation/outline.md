# Phase-I Review Presentation — outline

**Project:** KGCR — Knowledge Graph-Based Cloud Configuration Recommendation
**Course:** BCSE355L, Dr. Priya V · **Team:** Udit (lead), Manya, Tanmoy

Twelve slides, roughly 12 minutes plus questions. Every claim on a slide traces to a file in this
repository, listed under each slide so nothing is asserted from memory at the review.

---

**1. Title**
Project title, course, team, repository URL. One line of framing: recommend a compliant AWS
configuration from a workload described in business terms, and justify every choice as a traceable
path to a regulatory clause.

**2. The problem**
Cloud misconfiguration is a leading breach cause. Three tool families each cover one edge:
posture management sees only what is deployed, policy-as-code checks one resource at a time, FinOps
is compliance-blind. Nothing occupies the middle.
*Source:* `docs/Project_Report.md` §1.

**3. What the literature says**
Fifteen papers, 2023–2026, from IEEE, Springer, Elsevier, ACM and MDPI. Four findings: configuration
security is measured rather than reasoned about; graphs are used reactively after deployment;
compliance knowledge and configuration knowledge live in separate graphs; intent is always an input,
never recovered.
*Source:* `docs/Literature_Survey.md` synthesis section.

**4. Research gap**
One slide per student is optional; the shared point is that all fifteen treat configuration as
independent objects checked against rules, with intent supplied from outside.
*Source:* `docs/Research_Gap_Udit.md` and the two companion documents.

**5. Objectives**
Six, each with the measure that decides whether it is met. Flag which two already have results.
*Source:* `docs/Objectives.md`.

**6. Novelty**
One graph instead of four tools; defects defined as paths rather than properties; review reframed as
design with recovered intent; calibrated confidence instead of a single score; explanation as the
reasoning path itself.
*Source:* `docs/Novelty.md`.

**7. Diagram 1 — AWS Cloud Architecture**
Three accounts, the evidence pipeline (Config, CloudTrail and Cost and Usage Reports into S3, then
Lambda and Glue into Neo4j), Cognito and cross-account IAM for authentication, CloudWatch and
Budgets for monitoring, SNS for notification. Say out loud that this is the planning diagram.
*Source:* `architecture/AWS_Architecture.png`.

**8. Diagram 2 — Complete System Architecture**
The unified flow S1 to S10 with both entry conditions, the bounded advisor loop, the user gate, and
plan then apply.
*Source:* `architecture/System_Architecture.png`.

**9. Dataset**
Generated, not downloaded — and say so first, before being asked. 180 estates, 2,331 resources, 17
structural features, 7 intent axes, each estate carrying its originating intent as ground truth,
plus a 12-estate relational defect set. Estate-level splitting with a leakage guard.
*Source:* `dataset/dataset_description.md`.

**10. Results so far**
Two numbers, both reproducible from a seed:
- Multi-hop detection: the graph recovers 12 of 12 relational defects; Checkov's verdict on the
  sensitive sink is byte-identical to the clean parent in all 12 cases.
- Intent reconstruction: structural axes at 1.000 accuracy with ECE ≤ 0.052; `iam_shape` at 0.417
  with ECE 0.282 — confidently wrong where the estate carries no signal, which is why confidence is
  reported per field.
*Source:* `results/p4_df7_checkov_evidence.json`, `results/reconstruction_report.json`.

**11. AWS services plan and implementation status**
The 21-service table, with the honest split: a local Python pipeline plus authored-but-unapplied
Terraform today, everything else Phase-II. Expect the question and answer it on this slide rather
than in Q&A.
*Source:* `docs/Project_Report.md` §8–9.

**12. Contribution, repository and next steps**
Contribution matrix, branch model (`main` ← `develop` ← per-member feature branches), commit and PR
history, and the Phase-II critical path: encode the L1 controls, build the gold set, then the
recommender.
*Source:* `docs/Project_Report.md` §10–11, `CHANGELOG.md` §1.

---

## Preparation notes

- Each member must be able to explain their own five papers and their own commits without notes.
- Have `results/reconstruction_report.json` open in a tab — the calibration question is the most
  likely follow-up, and the reliability bins are in that file.
- The most likely challenge is the distance between the planned AWS architecture and what runs
  today. Slides 7 and 11 both state it, so the answer is already on the record.

**Status:** outline only. The slide deck itself has not been built.
