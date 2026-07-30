"""Defect taxonomy and injection engine (Phase 5, FD-05 §5).

This package takes the *clean* estates produced by :mod:`kgcr.corpus` and
injects enumerated defects over them, recording per-defect ground truth for the
seeded-recall metric (FD-04 §10). Two things it produces are load-bearing for
the project's central claim:

* **Per-defect ground truth** — every injected defect records its class, the
  resource(s) it was injected at, the control it breaches (as an FD-07 ``kg://``
  URI), and the expected finding.
* **The DF-7 relational set** — defects that exist only as a *path* through the
  estate graph, where every resource on the path is individually compliant.
  Single-resource policy engines score zero on this set by construction; a graph
  traversal recovers it. That contrast is the headline C1 evidence (FD-05 §7).
"""

from __future__ import annotations
