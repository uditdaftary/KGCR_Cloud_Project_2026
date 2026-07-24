"""KGCR — Knowledge Graph-Based Cloud Configuration Recommendation framework.

This package is the implementation skeleton established in Phase 0 (FD-08). At
this stage it provides the reproducibility spine that every later phase builds
on — deterministic seeding, canonical hashing, and run records keyed by
``(spec_hash, graph_version, model_version)`` — plus the CLI surface described
in the README. Subsystem logic (ontology, generator, advisor, recommender,
explainer) is added by later phases.
"""

from __future__ import annotations

from kgcr._version import __version__

__all__ = ["__version__"]
