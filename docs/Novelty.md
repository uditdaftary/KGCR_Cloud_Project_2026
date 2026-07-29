# Novelty Summary

**Project:** KGCR — Knowledge Graph-Based Cloud Configuration Recommendation
**Course:** BCSE355L Cloud Architecture Design Project, Phase-I

## What already exists

Three mature tool families each cover one edge of cloud configuration and none covers the middle.
Cloud security posture management products (Wiz, Prisma Cloud, Orca) detect violations in what has
already been deployed, and offer nothing at design time. Policy-as-code engines (Checkov, tfsec,
Prowler, OPA) check one resource at a time: they cannot recommend, they justify a finding only by
restating the rule that fired, and by construction they cannot see a defect that exists in the
relationship between two individually compliant resources. FinOps platforms (CloudHealth,
Cloudability) find waste but are blind to compliance, so their recommendations routinely conflict
with the security team's.

The literature surveyed for this project shows the same split. Configuration security is *measured*
through single-resource analysers; graph reasoning is applied *after* deployment to find attack
paths; compliance knowledge and configuration knowledge are modelled in separate graphs that are
never joined; and design intent is treated as an input a user supplies, never as something recovered
from the artefact.

## What is different here

**A better architecture — one graph instead of four tools.** Regulatory controls, the estate's
resources and dependencies, and the history of past runs live in a single graph representation.
Recommendation, review, cost reasoning and explanation are then operations over that one structure
rather than four products whose outputs a human has to reconcile.

**A new capability — multi-hop defect detection.** Because the estate is a graph, a defect can be
defined as a *path* rather than a property: a sensitive data store reachable from the internet
through a chain in which every individual resource passes its own policy check. A per-resource
engine cannot express this, and the gap is measured rather than asserted — on the current relational
defect set the graph recovers all 12 paths while Checkov, including its graph checks, returns a
verdict on the sensitive sink that is byte-identical to the clean parent estate.

**A reframing — review as design with recovered intent.** Existing review tools check a
configuration against fixed rules because they have no notion of what the configuration was *for*.
This project reconstructs the intent an estate was built to serve, then reviews the estate against
that reconstructed intent. Review and design become the same pipeline entered at different points.

**Honest confidence instead of a single score.** Intent reconstruction reports a calibrated
confidence per field, so a field the estate carries no evidence for is flagged for user confirmation
rather than guessed. The measured example is instructive: axes with structural evidence reconstruct
at 1.000 accuracy with expected calibration error at or below 0.052, while `iam_shape` — which the
generator leaves no structural trace of — reaches only 0.417 accuracy at 0.282 ECE, confidently
wrong. Surfacing that failure is the design goal, not an embarrassment to be smoothed over.

**Better explanation — the reasoning path itself.** An explanation is the extracted subgraph
connecting a configuration choice to the regulatory clause and the cost consequence, plus a
counterfactual naming the minimal change that flips the verdict. Because the compliance logic is
curated rather than learned, most of these explanations are exact, not approximations of a black
box. The rendering adapts to the audience — architect, auditor, learner — while the conclusion
stays identical, and that invariance is tested rather than claimed.

**Better automation with a stop condition.** Adversarial review between two separate model roles is
bounded: when the loop cannot converge, the system reports the disagreement as contested rather than
manufacturing agreement to look decisive.
