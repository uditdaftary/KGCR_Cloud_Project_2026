"""Intent reconstruction (Phase 8, FD-05 §8, FD-01 §7).

The framework's named contribution: recover an estate's originating *intent*
from its observed topology alone. Because Corpus A is generated intent-first,
every estate carries its true intent as free ground truth — so the evaluation is
self-contained (sample intent, generate, discard the intent, reconstruct, score
per field).

Two properties matter equally (FD-05 §8):

* **Accuracy** — per-field recovery against the known intent.
* **Calibration** — the confidence must be honest, because low-confidence fields
  escalate to user confirmation rather than proceed silently (FD-01 §7). An
  overconfident reconstructor is more dangerous than an inaccurate one, so the
  deliverable is a reliability diagram, not just an accuracy number.

The reconstructor here is a per-field classifier over hand-crafted structural
features — a legitimate baseline whose evaluation harness is the reusable part;
the GNN over the raw subgraph (P7's machinery) is the upgrade path.
"""

from __future__ import annotations
