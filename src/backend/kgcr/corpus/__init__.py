"""Corpus A — the intent-first synthetic estate generator (Phase 3, FD-05 §4A).

Generation is *intent-first*: an :class:`~kgcr.corpus.intent.Intent` is sampled
first, then a Terraform estate is rendered from it. Every estate therefore
carries its originating intent as free ground truth (FD-05 §8), which is exactly
what intent reconstruction (P8) needs.

At this phase the corpus is **clean** — no defects are injected (FD-05 §12 step
5). Defect injection is Phase 5 and plugs into the same estate representation.

Pipeline: ``sample intent → render estate → build graph``. The estate also
serialises to valid Terraform JSON so external tools (Checkov, tfsec — Phase 4)
can consume it, and the plan-JSON parser turns real ``terraform show -json``
output into the same graph type when terraform is available.
"""

from __future__ import annotations
