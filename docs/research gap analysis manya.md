Paper 1 — Banse, Kunz, Haas & Schneider (2023)

A Semantic Evidence-based Approach to Continuous Cloud Service Certification. Proceedings of the 38th ACM/SIGAPP Symposium on Applied Computing (SAC '23), 24–33. DOI 10.1145/3555776.3577600

Existing method

The authors collect real-time information from cloud services, which they call semantic evidence, and organise it against an extensible, vendor-neutral ontology of cloud resources and their security features. Generalising vendor- and scheme-specific terminology into this one shared model is what lets the same evidence be reused across certification schemes.
Their tool, called Clouditor, repeatedly collects this evidence from cloud resources and assesses it against generalised metrics elicited from the requirements of EUCS and CCMv4; requirements catalogues such as the German BSI C5 are handled the same way.
This is better than a normal audit because it monitors compliance continuously instead of checking only once.

Advantages

This turns certification from a yearly snapshot into an ongoing check, so problems surface as soon as a resource drifts out of compliance. Because the evidence is structured against one shared ontology, the same piece of evidence can support several different controls at once, which is a real improvement over older approaches that needed a separate test written for every single requirement.


Limitations


The ontology only covers the infrastructure layer, it does not yet look at application code or organisational documents, a gap the authors themselves later acknowledge in follow-up work. It also only ever tells you pass/fail against one fixed target value per metric, it has no notion of choosing between several acceptable configurations.

Research gap

The graph records what a resource's current setting is, not what it should be for the specific job that resource is doing. A public marketing bucket and a customer-data bucket that happen to have identical technical settings get the identical verdict, because nothing in the ontology represents what the resource is for. Recommendation needs that missing context; assessment alone does not.

Dataset

The paper does not use a public dataset. Instead, the authors collect live semantic evidence directly from cloud resources using their tool, Clouditor. This real-time data includes cloud configuration and security information, which is organized against their ontology of cloud resources and their security features. The collected evidence is then used to continuously monitor cloud services and check whether they comply with requirements drawn from catalogues such as EUCS, CCMv4 and the German BSI C5. Since the data is gathered from live cloud environments, the paper does not specify the dataset size, number of records, number of features, or provide a public download URL; its performance benchmark instead reports that up to 200,000 evidences can be processed in under a minute.

Possible improvement

Add "workload type" as a real node in the ontology (e.g. public asset store, regulated data store, internal test resource) and let the target value for each metric depend on that node, so the same evidence produces a context-specific recommendation instead of one universal pass/fail line.
________________________________________

Paper 2 — Joshi, Elluri & Nagar (2020)

An Integrated Knowledge Graph to Automate Cloud Data Compliance. IEEE Access 8, 148541–148555. DOI 10.1109/ACCESS.2020.3008964

Existing method

The authors analyse more than twenty compliance models that apply to cloud data and to IT generally — GDPR, PCI DSS, ISO 27001 and 27002, FedRAMP, CSA controls and others — and build them into a single machine-processable knowledge graph using Semantic Web technologies, natural language processing and text mining. The graph links four things together: a regulation, the cloud security standards that support it, the security controls that implement it, and the data threats those controls mitigate. SWRL rules and SPARQL queries then let an organisation ask which obligations under GDPR or PCI DSS its own policies actually satisfy. The authors' stated goal is a "cloud security comparator" that helps a customer choose a provider on security grounds.

Advantages

Regulation text normally needs an expert to read it; this turns it into something a reasoner can query, which is the difference between an annual manual exercise and an automated one. The graph also attacks the duplication problem directly: because overlapping regulations are linked through shared controls and threats in one model, a control evidenced once can be shown to serve several regulations at once, instead of being re-evidenced separately for each standard. The ontology and the collected policy documents were released publicly through two PURLs, and both still resolve — to the repositories ellurilavanya/CloudCompliance and ellurilavanya/CloudPrivacyDocuments — so the artefact can be reused rather than rebuilt.

Limitations

The validation reads the published privacy policies of Amazon, Google, IBM and Rackspace and populates the graph from key terms found in that prose. So what the system checks is what a provider says in a document, not how its deployed resources are actually configured — and an ontology class left empty is read as non-compliance, which conflates "not mentioned in the policy text" with "not implemented." The whole model also sits at the organisational level: no cloud resource, no configuration property and no runtime evidence appears anywhere in the graph.

Research Gap

The paper aims at recommendation, but recommends at the wrong granularity. It compares whole providers by which compliance models they support — and the authors' own next step is to add provider cost to that comparison. Nothing descends to an individual resource and the setting that resource ought to carry. There is also no representation of what the data is for: a regulation applies uniformly across every resource in scope, so the graph cannot express that two storage buckets governed by the same regulation should still be configured differently because they hold different things.

Dataset 

No benchmark dataset. The inputs are the text of the twenty-plus compliance models the authors surveyed, plus the published privacy policies of four cloud providers — Amazon, Google, IBM and Rackspace — used for validation. What the paper produces is an OWL/RDF ontology, released publicly at purl.org/csc/ontologyfiles with the collected policy documents at purl.org/csc/policydocuments. That is an artefact, not a labelled dataset: the paper reports no record count, no feature count and no size.

Possible Improvement

Keep the regulation → standard → control → threat backbone, but anchor it to concrete cloud resource types and their configurable properties, and add a deployment-intent node describing what each resource is for. A control then resolves to a specific property value on a specific resource instead of to a provider-level yes/no, compliance evidence comes from the resource's actual configuration rather than from a provider's policy prose, and the output becomes a ranked per-resource recommendation rather than a provider comparison.
________________________________________

Paper 3 — Banse, Fanta, Alonso & Martinez (2025)

EMERALD: Evidence Management for Continuous Certification as a Service in the Cloud. Proceedings of the 15th International Conference on Cloud Computing and Services Science (CLOSER 2025), 190–197. SciTePress. DOI 10.5220/0013348100003950. (EMERALD Horizon Europe project; preprint arXiv 2502.07330.)

Existing Method

EMERALD proposes a Certification-as-a-Service architecture built around a shared Certification Graph that includes information from cloud infrastructure, applications, organizational processes, and data. Its MARI component uses text similarity to recommend which security metrics best match different security controls. This allows the same security evidence to be reused across different certification standards, such as BSI C5, EUCS, and AI-specific certification catalogues.

Advantages

This is the first of the five papers to focus on recommendation instead of only checking compliance. MARI recommends which security metric should be used for each control, instead of asking a person to decide it manually. The framework has also been tested in four real deployment projects, including IaaS, PaaS, SaaS, and a hybrid cloud-edge financial sector environment, giving it broader practical use than a single laboratory demonstration.

Limitations

MARI matches controls and metrics based on how similar their text is, instead of checking whether they actually measure the same security requirement. As a result, two controls may have similar wording but different meanings, or different wording but the same meaning. At the time the paper was written, the framework was only partially completed, and the results from the pilot projects were not yet available.

Research Gap

The system recommends which security metric matches a control, but it does not recommend the actual resource configuration needed to satisfy that metric. Users still have to manually convert the recommendation from "this metric is relevant" to "set this property to this value." The knowledge graph does not complete this final and most useful step.

Dataset

The EMERALD paper does not use a public dataset. Instead, it uses security evidence collected from four real-world deployment pilots as part of the EMERALD Horizon Europe project. These pilots include Infrastructure as a Service (IaaS), Platform as a Service (PaaS), Software as a Service (SaaS), and a hybrid cloud-edge financial sector environment. The framework collects certification evidence from infrastructure, applications, organizational processes, and data layers to evaluate continuous cloud certification. Since the data comes from real deployment environments, the paper does not provide a public dataset, dataset size, number of records, number of features, or a download URL.

Possible Improvement

Extend the matching process beyond control-to-metric mapping to metric-to-configuration mapping. This will allow the system to provide a specific configuration value as the final recommendation instead of stopping at "this metric is applicable here."
________________________________________

Paper 4 — Eldjou, Kitouni, Benmounah & Bennacer (2025)

Enhancing cloud native security: a knowledge graph approach for securing container runtimes. Cluster Computing 28, article 777. DOI 10.1007/s10586-025-05531-6

Existing Method

The authors developed a hybrid knowledge graph that combines rule-based threat detection with graph-based investigation. It uses kernel-level telemetry (through eBPF) and the Elastic Common Schema (ECS) to connect runtime events across containerized microservices. The system was tested in the investigation stage of a real cloud-native Security Operations Centre (SOC).

Advantages

Since the knowledge graph is built using live kernel-level telemetry instead of a static configuration file, it shows what a container is actually doing while it is running, not just what it was configured to do. In the SOC case study, this reduced the time needed to understand a security alert by 20%. It also allowed security analysts to ask cross-layer questions that normal SIEM rules cannot answer.

Limitations

The knowledge graph mainly focuses on past incidents. It helps analysts understand what has already happened, instead of helping them make better configuration decisions before deployment. The evaluation was done using only one SOC case study, and there is no public dataset, so it is not clear how well the approach works for different cluster sizes or workload types.

Research Gap

The knowledge graph can connect a runtime event to the security incident it caused, but it does not connect the incident to the configuration change that could have prevented it. Detection and recommendation are treated as separate tasks. The graph explains what went wrong, but deciding how to make the system more secure is still left to the human analyst.

Dataset

The paper does not use a public dataset. The knowledge graph is built from kernel-level runtime telemetry captured with eBPF from containerized microservices, normalized into the Elastic Common Schema so that events from different layers can be correlated. Evaluation was carried out inside the investigation stage of a single real cloud-native Security Operations Centre, which means the data is live operational telemetry from one deployment rather than a fixed benchmark. The paper therefore gives no dataset size, record count, feature count or download URL, and because there is only one deployment there is no basis for judging how the results transfer to other cluster sizes or workload types.

Possible Improvement

Use the results of completed investigations to improve a configuration recommendation layer built on the same knowledge graph. This way, every resolved incident can help improve the recommended baseline configuration for similar workloads, instead of only adding another record to the history of past incidents.
________________________________________

Paper 5 — Zhu, Chen, Kong, Zhong & Song (2024)

DocSecKG: A Systematic Approach for Building Knowledge Graph to Understand the Relationship Between Docker Image and Vulnerability. Advanced Intelligent Computing Technology and Applications (ICIC 2024), Lecture Notes in Computer Science vol. 14874, 392–404. DOI 10.1007/978-981-97-5618-6_33

Existing method

DocSecKG automatically tracks, downloads, scans and refreshes Docker Hub's official ("library") images, building a knowledge graph that links each image to the software packages it contains and the known CVEs those packages carry, giving a structured, always-updating view of the Docker ecosystem's security posture.

Advantages

Automating the whole tracking-scanning-updating pipeline means the graph stays current as new images and new CVEs appear, unlike a static, one-off vulnerability report. Linking images through their shared packages also makes it possible to see which vulnerabilities are systemic across many images at once, something a per-image scanner cannot show on its own.

Limitations

The scope is limited to Docker Hub's official library images  a small, relatively well-maintained slice of the ecosystem so the findings may not carry over to community or private-registry images, which is where most real-world risk sits. The graph also reports which images carry which known CVEs without weighing how severe each one actually is for a particular deployment.

Research gap

Knowing an image has a CVE is not the same as knowing whether that CVE matters for how the image is actually going to be used, or which of several vulnerable candidate images is the better choice. Every flagged image is treated the same regardless of exposure, so the graph is good for auditing a single image but cannot recommend a base image or a hardening step for a specific deployment.

Dataset

The DocSecKG paper uses data collected from Docker Hub's official ("library") Docker images and their associated Common Vulnerabilities and Exposures (CVEs). The system automatically downloads, scans, and updates these Docker images to build a knowledge graph that connects images, software packages, and known vulnerabilities. The dataset is created from live Docker Hub repositories and public CVE databases rather than a fixed benchmark dataset. The paper does not specify the dataset size, number of records, number of features, or provide a downloadable dataset URL, as the data is continuously updated from official Docker images and vulnerability sources.

Possible improvement

Add deployment-context nodes to the same graph  exposed ports, privilege level, network reachability so vulnerability severity can be re-ranked per deployment, letting the system recommend a specific replacement image or configuration change rather than just listing known vulnerabilities.
________________________________________

What these five papers say together

All five papers use knowledge graphs for different cloud security tasks. Paper 1 focuses on cloud resource evidence, Paper 2 integrates data-protection regulations, controls and threats into one graph, Paper 3 maps security controls to metrics, Paper 4 analyzes runtime security events, and Paper 5 links Docker images with vulnerabilities. However, none of these papers provide ranked, context-aware cloud configuration recommendations. Papers 2 and 3 come closest and are the most telling: Paper 2 explicitly sets out to build a recommender but stops at comparing whole cloud providers by the compliance models they support, and Paper 3 stops at telling you which metric applies to a control. Neither descends to the level of an individual resource and the setting it should carry.

Another common limitation is that none of the papers include the purpose of the cloud resource (deployment intent), such as how it will be used or what data it handles. Because of this, users still need to manually decide the best cloud configuration. This is the main gap that the Knowledge Graph-Based Cloud Configuration Recommendation (KGCR) system aims to solve by combining cloud configuration, security rules, runtime information, and deployment intent to generate clear, explainable, and ranked configuration recommendations.
