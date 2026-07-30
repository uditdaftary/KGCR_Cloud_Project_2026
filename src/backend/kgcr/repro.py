"""Deterministic seeding across the libraries a run might use.

A single call to :func:`seed_everything` fixes every RNG the pipeline could
touch, so that a run is reproducible from its seed alone. Libraries that are
not installed are skipped silently — the scaffolding depends on none of them,
but later phases (recommender, reconstruction) will, and this function already
covers them.

``PYTHONHASHSEED`` cannot be changed once the interpreter has started, so we do
not try to; instead :func:`hash_seed_is_fixed` lets callers (and tests) assert
that the process was launched with it pinned, which is how CI enforces it.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

__all__ = ["DEFAULT_SEED", "seed_everything", "hash_seed_is_fixed", "SeedReport"]

DEFAULT_SEED = 1729


@dataclass(frozen=True)
class SeedReport:
    """Which RNGs :func:`seed_everything` actually seeded.

    Booleans reflect what was present in the environment, making the seeding
    itself auditable and testable.
    """

    seed: int
    python_random: bool
    pythonhashseed: bool
    numpy: bool
    torch: bool


def hash_seed_is_fixed() -> bool:
    """True if ``PYTHONHASHSEED`` was pinned for this interpreter."""
    value = os.environ.get("PYTHONHASHSEED")
    return value is not None and value != "random"


def seed_everything(seed: int = DEFAULT_SEED) -> SeedReport:
    """Seed every RNG in reach and return a report of what was seeded.

    Seeds Python's :mod:`random` always; seeds numpy and torch (including CUDA)
    when importable. Does not raise if optional libraries are missing.
    """
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")

    random.seed(seed)

    numpy_seeded = _seed_numpy(seed)
    torch_seeded = _seed_torch(seed)

    return SeedReport(
        seed=seed,
        python_random=True,
        pythonhashseed=hash_seed_is_fixed(),
        numpy=numpy_seeded,
        torch=torch_seeded,
    )


def _seed_numpy(seed: int) -> bool:
    try:
        import numpy as np
    except ImportError:
        return False
    np.random.seed(seed)
    return True


def _seed_torch(seed: int) -> bool:
    try:
        import torch
    except ImportError:
        return False
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    return True
