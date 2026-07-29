# Architecture diagrams

The guidelines require **two** diagrams (p.3):

| Diagram | Required content | Status |
|---|---|---|
| 1 — AWS Cloud Architecture | How AWS services interact: data flow, storage, processing, authentication, notifications, monitoring | **Not yet drawn** |
| 2 — Complete System Architecture | The overall project workflow | **Not yet drawn** |

## Files present

The two condition flowcharts below were supplied as the components of Diagram 1 and are filed as
such. Each is provided as PNG (the format the guidelines name) and SVG (vector source).

| File | Content |
|---|---|
| `AWS_Architecture_condition1_design.{png,svg}` | Condition 1 — "design me a config for…": requirement decode → knowledge-graph query → spec → advisor review loop → dependency graph → user acceptance → Agent 1 deploys |
| `AWS_Architecture_condition2_review.{png,svg}` | Condition 2 — "what's wrong with my config": Agent 2 harvests the live config → spec → advisor review loop → dependency graph → comparison against stored config → XAI defect explanation → user acceptance → Agent 1 deploys |

Together they cover both modes of the unified flow (FD-01).

## Note on Diagram 1

These two charts describe the *system workflow* — the stages a request passes through and the
decision points between them. The guidelines' Diagram 1 asks specifically for AWS **service
interaction**: which services carry the data, where it is stored, what processes it, how users are
authenticated, how notifications and monitoring work. That diagram does not exist yet, and it is a
mandatory item. Source material for it is PMD §6 (three-account topology; AWS Config + CloudTrail +
Cost & Usage Reports → S3 → Lambda/Glue ETL → Neo4j; cross-account IAM roles) and `src/aws/`.
