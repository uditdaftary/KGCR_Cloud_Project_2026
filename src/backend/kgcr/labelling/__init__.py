"""Weak-supervision labelling over the corpus (Phase 4, FD-05 §6).

The design (FD-05 §6) runs open-source policy engines — Checkov, tfsec, Prowler,
AWS Config rules — as programmatic labelling functions and combines them into
probabilistic labels, using inter-engine agreement as a confidence signal.

This module implements the slice that runs without cloud credentials or a
Terraform toolchain: **Checkov as a static labelling function** over the
plan-shaped ``.tf.json`` the corpus already emits. Its purpose here is narrow
and load-bearing — supply the *empirical* half of the DF-7 gate that P5 could
only assert by construction:

> On the DF-7 set a real policy engine (Checkov, including its CKV2 graph
> checks) produces no new finding about the sink that has become
> exfiltration-reachable — its verdict is byte-identical to the compliant
> parent — while a graph traversal recovers the path.

Honest limitations, stated rather than hidden (FD-05 §11):

* Only Checkov is wired. tfsec (a Go binary) and Prowler (needs a live AWS
  account) are deferred, so *inter-engine* agreement is not yet available — the
  weak-supervision label model needs >=2 engines and is left for when they are.
* Checkov's ``.tf.json`` path evaluates single-resource checks inconsistently on
  our interpolated configs, so a fair DF-1..DF-4 *recall* baseline needs HCL or
  real ``terraform plan`` JSON as input and is deferred. The DF-7 sink-invariance
  result above does not depend on it.
"""

from __future__ import annotations
