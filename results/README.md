# Results

Every file here is produced by a script and reproduces from its seed (default 1729) on the
synthetic corpus. None describes a real estate.

| File | Phase | Produced by |
|---|---|---|
| `p4_df7_checkov_evidence.json` | P4 × P5: graph versus Checkov on relational defects | `kgcr.labelling` (needs the `labelling` extra) |
| `reconstruction_report.json` | P8: per-field accuracy and calibration | `python src/ml_model/train.py` |
| `recommender_report.json` | P7: rankers versus baselines, mask contents | `python src/ml_model/train_recommender.py` |
| `advisor_report.json` | P6: rule-floor recall; LLM section and sycophancy gate | `python src/ml_model/run_advisor.py` |
| `dashboard.html` | Visual summary of the reports above | `python src/frontend/build_dashboard.py` |
| `llm_fixtures/` | Recorded Gemini responses, replayed offline | `run_advisor.py` with `KGCR_LLM_LIVE=1` |

`advisor_report.json` holds the recorded live run (16 Gemini calls). `NOT_RUN` in either field means
no live call was made; `llm_fixtures/` replays the recorded responses offline.
