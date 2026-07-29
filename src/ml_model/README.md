# ML model — intent reconstruction (P8)

Entry points for the intent reconstructor. Thin wrappers over
`kgcr.reconstruction`; the logic and its tests live in the library
([../backend/kgcr/reconstruction/](../backend/kgcr/reconstruction/)).

```bash
python src/ml_model/preprocessing.py --count 180   # generate the corpus into dataset/processed/
python src/ml_model/train.py --count 180           # fit, write model.pkl + the evaluation report
python src/ml_model/predict.py --index 0           # reconstruct one estate's intent
```

## `model.pkl` is not committed

The guidelines' sample tree lists `model.pkl` alongside the three scripts. It is
deliberately **not** in version control here: it is 5.7 MB of pickled forests
that re-derive byte-for-byte from `train.py --count 180` at the default seed, so
the seed is the artifact worth versioning, not the binary — the same argument as
[../../dataset/README.md](../../dataset/README.md). What *is* committed is the
result the model produces: [../../results/reconstruction_report.json](../../results/reconstruction_report.json).

Run `train.py` before `predict.py`; it errors clearly if the model is absent.

## What the numbers say

On the 180-estate corpus at the default seed, structurally-encoded axes
(archetype, AZ spread, network layout, logging) reconstruct at 1.000 with
ECE ≤ 0.052. `iam_shape` — which the generator leaves no structural trace of —
reconstructs at 0.417 with ECE 0.282, overconfident on no signal. That
overconfidence is the point of reporting calibration rather than accuracy alone.
