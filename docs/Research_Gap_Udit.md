# Individual Research Gap Analysis — Udit

**Papers 1–5** of the team literature survey.
**Project:** KGCR — Knowledge Graph-Based Cloud Configuration Recommendation
**Course:** BCSE355L Cloud Architecture Design Project, Phase-I

The analysis below is my own reading of each paper. Where I state a limitation or a gap, it is an
inference I am drawing from what the paper reports, not a passage copied from the paper's own
future-work section.

---

## Paper 1 — Verdet, Hamdaqa, Da Silva & Khomh (2025)

*Assessing the adoption of security policies by developers in terraform across different cloud
providers.* Empirical Software Engineering 30. Springer. DOI 10.1007/s10664-024-10610-0

**Existing method.** An empirical study of how far developers actually adopt scripted security
practices in Terraform. The authors scan 812 open-source GitHub projects across AWS, Azure and
Google Cloud with two static analysers, Checkov and Tfsec, and count which policy categories are
honoured and which are neglected.

**Advantages.** The scale and the cross-provider comparison are the strength: this is evidence about
real practice rather than opinion about it. Finding that access-policy controls are widely adopted
while encryption-at-rest controls are widely neglected gives a concrete, actionable ordering of
where remediation effort should go, and the same measurement can be repeated on any Terraform
codebase.

**Limitations.** The study can only see what its two analysers can express. Both are single-resource
rule engines, so the study measures conformance to per-resource rules and inherits their blind
spots. Open-source repositories are also unlikely to resemble a regulated production estate, where
the pressure and the review process are different — the authors are careful about scope, but the
population is what it is.

**Research gap.** The study measures *whether* a policy was adopted and never *why* a particular
resource needed it. Because adoption is scored against rule text, a configuration that is compliant
resource-by-resource but unsafe in combination is scored as adopted. There is also no way to
distinguish a genuine omission from a deliberate, justified exception, since neither the workload's
purpose nor the control that governs it is represented anywhere.

**Possible improvement.** Carry the workload's intent and the controls binding it alongside the
configuration, so adoption is measured against what the estate is *for*. That turns a rule count
into a judgement and makes justified exceptions expressible rather than invisible.

---

## Paper 2 — Wen & Ping (2025)

*PHOENIX: Misconfiguration Detection for AWS Serverless Computing.* IEEE Transactions on Cloud
Computing 13, 922–934. DOI 10.1109/TCC.2025.3577211

**Existing method.** PHOENIX first characterises 733 real AWS Serverless Application Model
configuration files, then learns configuration patterns from a uniform representation of them and
flags configurations that deviate from those learned patterns. It is evaluated on 35 injected and 70
real-world confirmed misconfigurations.

**Advantages.** The detection numbers are strong — 100% of injected and 97.14% of real-world
misconfigurations — and the approach is well grounded, because the pattern model is built on a
characterisation study of real configurations rather than on assumptions about what serverless
configurations look like. Learning patterns also means the detector is not limited to the rules
somebody remembered to write.

**Limitations.** Learned patterns describe what is *common*, not what is *correct*. If an insecure
pattern is widespread in the corpus — and misconfiguration is common precisely because it is easy —
then the detector will treat it as the norm and flag the secure minority as deviant. The scope is
also a single schema at function level, so it does not see the surrounding infrastructure the
function depends on.

**Research gap.** Deviation from the majority is not violation of a control. A flagged deviation
carries no link to a regulatory clause, so a finding cannot be defended to an auditor: the system
can say "this is unusual" but not "this breaches PCI-DSS requirement X, and here is the path". That
distinction is exactly what an audit requires.

**Possible improvement.** Ground detection in curated compliance knowledge rather than corpus
frequency, and attach the controlling clause to every finding. Pattern learning then becomes a
useful prior for ranking rather than the authority deciding what is wrong.

---

## Paper 3 — Nekrasov, Fossati, Kumara, Tamburri & van den Heuvel (2026)

*IaC Generation with LLMs: An Error Taxonomy and A Study on Configuration Knowledge Injection.*
ACM Transactions on Software Engineering and Methodology. DOI 10.1145/3817608

**Existing method.** The authors attack the low success rate of LLM-generated Terraform by injecting
structured configuration knowledge, progressing from naive retrieval-augmented generation to Graph
RAG with semantically enriched components and modelled inter-resource dependencies. They extend the
IaC-Eval benchmark with cloud emulation and automated error analysis, and contribute an error
taxonomy for LLM-assisted IaC.

**Advantages.** The gain is large and clearly attributed: technical validation success rises from a
27.1% baseline to 75.3%, and overall success to 62.7%. The error taxonomy is reusable independently
of the technique, and the finding that a *graph* representation of inter-resource dependencies helps
more than flat retrieval is directly relevant to any project representing an estate as a graph.

**Limitations.** The paper's own headline limitation is the more interesting result: intent
alignment plateaus even as technical correctness climbs. The authors name this the
"Correctness–Congruence Gap" — the model becomes a proficient coder while remaining a limited
architect. Knowledge injection is also one-directional; the model consumes injected knowledge but is
never required to justify a choice against it.

**Research gap.** Intent is treated purely as an input the user supplies and the model may or may
not honour. Nothing in the pipeline recovers intent from the artefact that was produced, and nothing
checks the artefact back against the intent. So the gap the authors measure is precisely the one
their method cannot close, because the loop only runs in one direction.

**Possible improvement.** Close the loop: reconstruct the intent implied by the generated
configuration and compare it against the stated intent, escalating the fields where the two diverge.
Congruence then becomes a measurable, enforceable property instead of a residual error the benchmark
reports.

---

## Paper 4 — Hu, Bu, Wong, Sood, Smiley & Rahman (2023)

*Characterizing Static Analysis Alerts for Terraform Manifests: An Experience Report.* 2023 IEEE
Secure Development Conference (SecDev), 7–13. DOI 10.1109/SecDev56634.2023.00014

**Existing method.** An industrial experience report. The authors investigate 491 static analysis
alerts across 10 open-source and one proprietary Terraform repository, derive a category taxonomy,
and collect practitioner perceptions of whether each category is worth acting on.

**Advantages.** The practitioner dimension is what makes this paper useful. It reports not just what
tools emit but how developers respond, and finds that response varies sharply by alert category —
which reframes alert fatigue as a triage problem rather than a volume problem. Ten categories, five
of them security-related, give a usable structure for reasoning about Terraform alerts.

**Limitations.** The sample is small and the industrial context is a single organisation, so the
practitioner perceptions may not generalise. More fundamentally, the study analyses alerts the tools
already emit, which means it cannot characterise the defects those tools never report at all — the
false negatives are invisible to this methodology by construction.

**Research gap.** The paper reports that Terraform resources **with dependencies** attract more
static analysis alerts than resources without. That is the relational signal appearing directly in
the data, yet the analysis stays per-manifest: dependencies are treated as a property that
correlates with alert count rather than as the structure a defect might live in. Nobody follows the
dependency edge to ask what the chain as a whole permits.

**Possible improvement.** Build the dependency graph explicitly and define defects over paths
through it, so that a chain of individually clean resources can still be flagged. The paper's own
correlation is the argument for doing this; it stops one step short.

---

## Paper 5 — Chu, Wan, Li, Wu, Zhang, Sui, Xu & Jin (2024)

*Graph Neural Networks for Vulnerability Detection: A Counterfactual Explanation.* Proceedings of
the 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis (ISSTA), 389–401.
DOI 10.1145/3650212.3652136

**Existing method.** CFExplainer explains a GNN-based vulnerability detector by searching for the
minimal perturbation to the input code graph that changes the model's prediction. This is
counterfactual rather than factual reasoning: instead of highlighting which features mattered, it
answers what would have to change for the verdict to flip.

**Advantages.** The counterfactual framing is a genuine improvement over feature-attribution
explainers, because a minimal perturbation localises a root cause rather than merely marking salient
regions. For a developer the output is closer to actionable — it points at what to change, not just
where the model looked.

**Limitations.** The explanation is a post-hoc search over a black box, so its faithfulness is
approximate: it explains the model's behaviour, which is only as trustworthy as the model. The
counterfactual is also a graph edit, and a minimal edit to a code property graph is not necessarily
a change a developer can actually make in the source.

**Research gap.** The explanation is discovered from a learned model, never read from curated domain
knowledge, so it can say what would flip the prediction but never cite an authority for why the
flagged structure is wrong in the first place. In a compliance setting that is fatal: an auditor
needs the clause, not the model's sensitivity.

**Possible improvement.** Where the underlying logic is curated rather than learned, a counterfactual
can be computed exactly instead of searched for approximately, and it can name the control it
resolves. Combining an exact counterfactual with the reasoning path that produced it gives an
explanation that is both actionable and defensible — neither property alone is enough for audit.

---

## What these five papers say together

Papers 1, 2 and 4 all analyse cloud configuration through tools that see one resource at a time, and
all three run into the same wall from different directions: the rule engine's expressiveness bounds
the study (Paper 1), majority behaviour is mistaken for correctness (Paper 2), and the relational
signal shows up in the data but is not followed (Paper 4). Paper 3 shows the problem is not solved
by better generation either — correctness rises while intent alignment does not. Paper 5 shows that
even a strong explanation technique cannot cite an authority when its reasoning is learned rather
than encoded.

The common thread is that all five treat configuration as a set of independent objects checked
against rules, with intent supplied from outside and never recovered. Representing the estate,
the controls that govern it and the intent behind it in one graph addresses all five gaps at
once, which is the direction this project takes.
