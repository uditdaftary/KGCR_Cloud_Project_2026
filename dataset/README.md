# Dataset

The corpus is **generated, not downloaded**. No external dataset is used, and no
real financial-sector data is involved (FD-05).

| | |
|---|---|
| `raw/` | Inputs to generation: the intent space and sampler are code, so the only raw input is the seed. Mined and adversarial corpora (FD-05 corpus C/D) land here when acquired. |
| `processed/` | Generated estates — per estate a Terraform JSON, its ground-truth intent, and its dependency graph, plus `manifest.json`. |

Regenerate the processed corpus deterministically:

```bash
python src/ml_model/preprocessing.py --count 180 --seed 0
```

The generated estates are not committed — they re-derive exactly from
`(count, seed)`, so the seed is the artifact worth versioning, not the output.
`manifest.json` is kept as the record of what a run produced.

Full dataset details in the guideline format (name, source, size, records,
features, type, licence, purpose, preprocessing) go in
`dataset_description.pdf` — not yet written.
