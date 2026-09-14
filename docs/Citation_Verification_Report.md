# Citation Verification Report — Research Gap Analyses (Udit, Manya)

Verified 31 July 2026 against Crossref metadata (`api.crossref.org/works/<DOI>`), Semantic Scholar,
arXiv, and publisher/author pages. Every DOI in both documents was resolved individually.

**Headline: none of the 10 papers is hallucinated.** All exist, all DOIs resolve to the paper named.
Six citation-level defects were found, all in Manya's document except one numeric slip in Udit's.

**Status of fixes: all applied.** Udit's two files were corrected directly (§2.6 and §4 below).
Manya's four corrections were applied to `research gap analysis manya.md` at the team lead's
direction, rather than handed to her as replacement text — a departure from CLAUDE.md §2, which
says each student authors their own sections. Manya should review that file before it goes further;
this report is the evidence trail for every line that changed. The survey/gap-document conflict
recorded in §5 has also been resolved. Sections below record the decision taken on each item, not
the options.

---

## 1. Verification table

| # | Owner | Cited as | DOI resolves | Metadata match | Verdict | PDF |
|---|---|---|---|---|---|---|
| 1 | Udit | Verdet, Hamdaqa, Da Silva & Khomh (2025), *Empirical Software Engineering* 30 | Yes | Authors/title/venue/year exact | **Verified** | Yes |
| 2 | Udit | Wen & Ping (2025), *IEEE Trans. Cloud Computing* 13, 922–934 | Yes | Exact, incl. vol/pages (13(3), 922–934) | **Verified** | No (IEEE paywall) |
| 3 | Udit | Nekrasov, Fossati, Kumara, Tamburri & van den Heuvel (2026), *ACM TOSEM* | Yes | Authors/title/venue/year exact | **Verified**, one numeric slip in prose | Yes |
| 4 | Udit | Hu, Bu, Wong, Sood, Smiley & Rahman (2023), *IEEE SecDev*, 7–13 | Yes | Exact, incl. pages | **Verified** | Yes |
| 5 | Udit | Chu, Wan, Li, Wu, Zhang, Sui, Xu & Jin (2024), *ISSTA*, 389–401 | Yes | Exact, incl. pages | **Verified** | Yes |
| 6 | Manya | Banse, Kunz, Haas & Schneider (2023), *SAC '23*, 24–33 | Yes | Exact, incl. pages | **Verified**; one model name unverified (§2.5) | No (ACM paywall) |
| 7 | Manya | Joshi, Elluri, Nagar & Hendre, *IEEE Access* 8, 148541–148555 | Yes | Title/venue/vol/pages exact; **author list wrong, year missing** | **Real but citation wrong — and the summary describes a different paper** | Yes |
| 8 | Manya | Banse, Fanta, Alonso & Martinez (2025), arXiv 2502.07330 | Yes | Authors/title exact; all technical claims confirmed against full text | **Verified**, but cite the peer-reviewed version | Yes (×2) |
| 9 | Manya | Eldjou, Kitouni, Benmounah & Bennacer (2025), *Cluster Computing* 28, art. 777 | Yes | Exact | **Verified**; dataset paragraph is wrong text | No (Springer paywall) |
| 10 | Manya | Zhu, Chen, Kong, Zhong & Song (2024), *ICIC 2024*, LNCS, 392–404 | Yes | Exact, incl. pages | **Verified** | No (Springer paywall) |

---

## 2. Defects that must be fixed

### 2.1 Manya, Paper 2 — the description belongs to a different paper (most serious)

The heading cites **Joshi, Elluri & Nagar (2020), "An Integrated Knowledge Graph to Automate Cloud
Data Compliance", IEEE Access 8, 148541–148555**. That paper is real and is about a knowledge graph
of *data-compliance regulations* (GDPR/PCI DSS style controls, threats, mitigations).

The prose underneath describes something else entirely:

> "CertGraph is a proposed knowledge graph that collects security information from different sources,
> such as cloud infrastructure, application source code, and AI models…"

That is **CertGraph**, a separate paper:

> Schöberl, Banse, Geist, Kunz & Pinzger (2024). *CertGraph: Towards a Comprehensive Knowledge Graph
> for Cloud Security Certifications.* MODELS '24 Companion Proceedings, ACM/IEEE.
> DOI 10.1145/3652620.3687795

The "short vision paper", "does not provide a dataset or performance results", and the
cloud-infra + source-code + AI-models ontology all match CertGraph, not Joshi 2020.

**Decision: keep Joshi 2020, rewrite the analysis from the paper itself.** CertGraph was the other
candidate and would have fixed the date preference (§2.2) at the same time, but it is a **two-page**
MODELS companion poster (pp. 76–77) whose full text is not obtainable — writing its analysis from an
abstract would repeat the error being fixed. Joshi 2020 is a full 15-page open-access IEEE Access
journal paper, the PDF is now in `docs/papers/`, and it fits KGCR's argument better than expected:
its own stated goal is a recommendation system, and it stops at ranking *providers* rather than
resource configurations. Applied: the whole Paper 2 entry in `research gap analysis manya.md` was
rewritten from the PDF, the author list cut to the correct three, and the year added.

### 2.2 Manya, Paper 2 — author list and year

- Crossref, Semantic Scholar, and the authors' own UMBC eBiquity lab page all list **three** authors:
  Karuna Pande Joshi, Lavanya Elluri, Ankur Nagar. **There is no Hendre on this paper** — drop it.
- The heading is the only one in either document with **no year**. It is **2020**.
- 2020 sits outside the CLAUDE.md preferred window (2023–2026). Flagging as a policy matter, not a
  correctness one. Note that CertGraph (2024) would resolve both this and §2.1 at once.

### 2.3 Manya, Paper 4 — dataset paragraph is a copy of Paper 3's

Line 114 of `docs/research gap analysis manya.md` is verbatim identical to line 85. The Paper 4
dataset section describes **EMERALD's four Horizon Europe pilots** when Paper 4 is the Eldjou
container-runtime paper. The correct text should describe eBPF kernel-level telemetry collected in a
single cloud-native SOC case study, with no public dataset — which the Limitations paragraph on
line 106 already says correctly.

### 2.4 Manya, Paper 3 — cite the published version, not the preprint

arXiv 2502.07330 is real and its arXiv page carries "Accepted for publication at CLOSER 2025". The
citable version is:

> Banse, Fanta, Alonso & Martinez (2025). *EMERALD: Evidence Management for Continuous Certification
> as a Service in the Cloud.* Proceedings of CLOSER 2025, 190–197. SciTePress.
> DOI 10.5220/0013348100003950

arXiv is not on the CLAUDE.md approved venue list; CLOSER/SciTePress (Scopus-indexed) is.

### 2.5 Manya, Paper 1 — "Cloud Property Graph" attribution removed rather than resolved

Whether the SAC '23 paper uses the Cloud Property Graph could not be settled: the ACM full text is
paywalled. What *is* established is that the paper's own model is an **extensible, vendor-neutral
ontology of cloud resources and their security features**, and that the **Cloud Property Graph** is a
separate earlier contribution (Banse, Kunz, Schneider & Weiss, IEEE CLOUD 2021; arXiv 2206.06938)
which later Fraunhofer work cites as its own reference.

**Decision: state what the paper states and drop the CPG name entirely.** That makes the entry
unambiguously correct without needing the paywalled text — a hedge would be worse than a clean
statement. Applied in both places the attribution appeared — the Existing-method paragraph and the
Dataset paragraph — which now name the ontology, cite EUCS and CCMv4 as the catalogues the metrics
come from, and add the paper's own benchmark (up to 200,000 evidences processed in under a minute).

Two claims in this entry check out and are kept: **Clouditor** is the tool, and **BSI C5** is
genuinely named in the paper as a source of requirements. The correction additionally names **EUCS
and CCMv4** as the catalogues the metrics are elicited from, which the abstract confirms.

### 2.6 Udit, Paper 3 — numbers conflated

The document says:

> "technical validation success rises from a 27.1% baseline to 75.3%, and overall success to 62.7%"

The paper's own abstract, read from the downloaded PDF, says: baseline LLM performance was poor
(**27.1% overall success**); knowledge injection increased technical validation success to **75.3%**
and overall success to **62.6%**. The string "62.7" does not occur in the paper.

**Fixed.** `docs/Research_Gap_Udit.md` and the survey's row 3 now both read "overall success rises
from a 27.1% baseline to 62.6%, with technical validation success reaching 75.3%". Verified: the
string "62.7" no longer appears in either file, and every row of all three survey tables has the
correct column count.

*(An earlier draft of this report claimed survey row 3 was structurally malformed — missing its
`| 3 |` index cell. It was not; a display filter used while reading the file had stripped that cell.
The row was correct as committed.)*

---

## 3. Claims spot-checked and confirmed

| Claim | Source | Result |
|---|---|---|
| 812 GitHub projects, Checkov + Tfsec, access policy most adopted / encryption-at-rest most neglected | Udit P1 | Confirmed |
| 733 AWS SAM files; 35 injected + 70 real misconfigurations; 100% and 97.14% detection | Udit P2 | Confirmed verbatim from abstract |
| 491 alerts, 10 OSS + 1 proprietary repo, 10 categories (5 security), resources with dependencies attract more alerts | Udit P4 | Confirmed |
| MARI, text-similarity control→metric mapping, four pilots (IaaS/PaaS/SaaS + hybrid cloud-edge financial), Certification Graph, BSI C5 | Manya P3 | Confirmed against full text |
| 20% reduction in threat-analysis latency vs. SIEM workflow, eBPF + ECS, single SOC case study | Manya P4 | Confirmed |

## 4. Also worth knowing

Udit's Paper 1 has a published **Correction** (Springer, DOI 10.1007/s10664-025-10667-5, September
2025). Checked: it changes only the copyright-holder line on the article, nothing scientific. The
812-project count and the access-policy / encryption-at-rest ordering cited in the gap analysis are
unaffected. The article has no page range — it is **article 74, issue 3**, so cite it as *Empirical
Software Engineering 30(3), article 74* rather than with page numbers.

---

## 5. The survey and the gap documents named different papers — resolved

**The problem.** `Literature_Survey.md` listed five papers under "Manya — papers 6–10" —
Vo/Dao/Fukuda, Bühler, Elmiger, Palma, Zhong — and **none of them was in
`research gap analysis manya.md`.** Manya's five are Banse SAC '23, Joshi 2020, EMERALD, Eldjou and
DocSecKG. The two documents claimed different things about the same five slots, and Eldjou et al.
(2025) appeared as both Manya's Paper 4 and the survey's paper 15, a Tanmoy slot.

**Which document was right.** The survey is the older one: authored by Udit (commit `e0fce12`) as a
proposed starting point, and its own preamble says each student rewrites their own five. Manya then
chose a different five and committed them (`fca72cc`, `ace052f`). So Manya's file was the current
truth and the survey rows were stale.

**Resolved as follows.** Survey rows 6–10, both in the reference list and in the table, are now
Manya's five, written from her corrected gap analysis and the sources verified in this report. Three
knock-on changes were needed:

- **Line 6 rewritten.** It asserted *"15 papers, all published 2023–2026"*, which Joshi 2020 breaks.
  It now names Joshi 2020 as a deliberate pre-2023 exception and gives the reason — the closest prior
  attempt at knowledge-graph-driven cloud security *recommendation*, stopping at provider
  granularity, which is exactly what this project changes. SciTePress was added to the venue list for
  the CLOSER version of EMERALD.
- **Slot 15 is vacant, not filled.** Eldjou moved to Manya's slot 9, so Tanmoy needs a fifteenth
  paper. Nothing was substituted on his behalf — the reference list and the table both mark the slot
  vacant and point at `feature/tanmoy`.
- **The ⚑ convention changed.** It previously meant "full text not read". It now means the
  bibliographic record is verified but no open-access full text could be obtained, so the cells come
  from the abstract plus the owning student's analysis. Papers 6, 9 and 10 carry it.

Verified after the change: 15 table rows numbered 1–15 with no duplicates, and every row in all
three tables has the correct column count.

**Dropped, and worth keeping somewhere.** The five displaced papers (Vo/Dao/Fukuda on LLM Terraform
smell detection, Bühler's TerraDS corpus, Elmiger's Microsoft-tenant attack graphs, Palma's
progressive attack graphs, Zhong's GNN-for-IDS survey) had written analyses and are recoverable from
git history at `e0fce12`. TerraDS in particular is a dataset paper this project may still want.

---

## 6. PDFs retrieved

Saved to `docs/papers/`. Six of the ten papers obtained from open-access sources (seven files —
EMERALD appears in both preprint and published form); no paywall was circumvented.

Every file below was opened and its title page checked against the citation. An earlier version of
this report listed a Joshi 2020 PDF fetched from a guessed eBiquity URL; that file turned out to be
an unrelated human-robot-interaction paper and has been replaced with the correct IEEE Access
article (15 pages, title page confirming all three authors).

| File | Source |
|---|---|
| `Udit_P1_Verdet_2025_Terraform_Security_Policies.pdf` | Europe PMC (open access) |
| `Udit_P3_Nekrasov_2026_IaC_Generation_with_LLMs.pdf` | arXiv 2512.14792 (author preprint of the TOSEM paper) |
| `Udit_P4_Hu_2023_Terraform_Static_Analysis_Alerts.pdf` | Author copy, akondrahman.github.io |
| `Udit_P5_Chu_2024_CFExplainer_ISSTA.pdf` | arXiv 2404.15687 |
| `Manya_P2_Joshi_2020_Integrated_KG_Cloud_Data_Compliance.pdf` | IEEE Xplore (IEEE Access is open access, CC-BY) |
| `Manya_P3_Banse_2025_EMERALD.pdf` | arXiv 2502.07330 |
| `Manya_P3_Banse_2025_EMERALD_CLOSER.pdf` | SciTePress (open access, the citable version) |

Not obtainable openly — use the landing page:

| Paper | Landing page |
|---|---|
| Udit P2 — PHOENIX | https://doi.org/10.1109/TCC.2025.3577211 (IEEE paywall) |
| Manya P1 — Banse SAC '23 | https://doi.org/10.1145/3555776.3577600 (ACM paywall) |
| Manya P4 — Eldjou | https://doi.org/10.1007/s10586-025-05531-6 (Springer paywall) |
| Manya P5 — DocSecKG | https://doi.org/10.1007/978-981-97-5618-6_33 (Springer paywall) |

All four are reachable through the VIT library's IEEE/ACM/Springer subscriptions.
