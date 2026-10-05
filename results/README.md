# Results

Every file here is produced by a script and reproduces from its seed (default 1729) on the
synthetic corpus. None describes a real estate.

| File | Phase | Produced by |
|---|---|---|
| `p4_df7_checkov_evidence.json` | P4 × P5: graph versus Checkov on relational defects | `kgcr.labelling` (needs the `labelling` extra) |
| `reconstruction_report.json` | P8: per-field accuracy and calibration | `python src/ml_model/train.py` |
| `recommender_report.json` | P7: rankers versus baselines, mask contents | `python src/ml_model/train_recommender.py` |
| `advisor_report.json` | P6: rule-floor recall; LLM section and sycophancy gate | `python src/ml_model/run_advisor.py` |
| `llm_fixtures/` (once recorded) | Recorded Gemini responses, replayed offline | `run_advisor.py` with `KGCR_LLM_LIVE=1` |

In `advisor_report.json`, `"llm": "NOT_RUN"` and `"sycophancy_gate": "NOT_RUN"` mean exactly that:
no live model call has been made, and no result is claimed.
