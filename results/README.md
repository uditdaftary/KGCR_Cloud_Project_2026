# Results

Every file here is produced by a script and reproduces from its seed (default 1729) on the
synthetic corpus. None describes a real estate.

| File | Phase | Produced by |
|---|---|---|
| `p4_df7_checkov_evidence.json` | P4 × P5: graph versus Checkov on relational defects | `kgcr.labelling` (needs the `labelling` extra) |
| `reconstruction_report.json` | P8: per-field accuracy and calibration | `python src/ml_model/train.py` |
| `recommender_report.json` | P7: rankers versus baselines, mask contents | `python src/ml_model/train_recommender.py` |
| `advisor_report.json` | P6: rule-floor recall; LLM section and sycophancy gate | `python src/ml_model/run_advisor.py` |
| `corpus_d_report.json` | P4: rule floor against Checkov on TerraGoat and CloudGoat | `python src/ml_model/run_corpus_d.py` (needs the `adversarial` extra and the clones from `acquire_corpus_d.py`) |
| `labeller_agreement.json` | P4: rule floor, Checkov (plan JSON) and Trivy on seeded and clean estates | `python src/ml_model/run_labeller_agreement.py` (Checkov, Trivy, Terraform) |
| `labeller_agreement_tfjson.json` | The same with Checkov reading `.tf.json`: recall 0 of 24, the evidence that plan JSON is the fair input | `... --checkov-input tfjson` |
| `explainer_report.json` | P9: invariance, counterfactual validity, sparsity, relational fidelity | `python src/ml_model/run_explainer_eval.py` |
| `gnn_ablation.json` | P7: a graph network against the forest, with an edge-free control | `python src/ml_model/gnn_ablation.py` (needs the `gnn` extra) |
| `dashboard.html` | Visual summary of the reports above | `python src/frontend/build_dashboard.py` |
| `llm_fixtures/` | Recorded Gemini responses, replayed offline (advisor passes and free-text intents) | `run_advisor.py`, `record_variants.py`, `kgcr design --statement`, with `KGCR_LLM_LIVE=1` |

`advisor_report.json` holds the recorded live run (16 Gemini calls). `NOT_RUN` in either field means
no live call was made; `llm_fixtures/` replays the recorded responses offline.
