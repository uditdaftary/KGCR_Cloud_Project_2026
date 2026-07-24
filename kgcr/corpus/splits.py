"""Estate-level train/validation/test splitting (FD-05 §9).

Splitting at the *resource* level leaks: two resources from one estate share
topology, tags and seed, so a model recognises the estate instead of learning
the pattern. The correct unit is the estate — and, more strictly, the *seed
family*, so structurally near-identical estates cannot straddle the boundary.

:func:`split_estates` partitions by seed family with a deterministic hash, and
:func:`check_split_integrity` proves the two properties reviewers check: no
estate appears in two splits, and no seed family straddles splits.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from kgcr.corpus.estate import Estate
from kgcr.hashing import canonical_hash

__all__ = ["Split", "CorpusSplit", "split_estates", "check_split_integrity"]


@dataclass(frozen=True, slots=True)
class Split:
    """Estate ids assigned to one split."""

    name: str
    estate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusSplit:
    """A train/validation/test partition over estate ids."""

    train: Split
    validation: Split
    test: Split

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "train": list(self.train.estate_ids),
            "validation": list(self.validation.estate_ids),
            "test": list(self.test.estate_ids),
        }


def _family_bucket(seed_family: str, salt: str) -> float:
    """Deterministic value in [0, 1) for a seed family."""
    digest = canonical_hash({"family": seed_family, "salt": salt})
    # Use the first 8 hex chars as a stable integer fraction.
    return int(digest[:8], 16) / 0x100000000


def split_estates(
    estates: Sequence[Estate],
    *,
    train: float = 0.70,
    validation: float = 0.15,
    salt: str = "kgcr-split-v1",
) -> CorpusSplit:
    """Partition estates into train/validation/test by seed family.

    Every estate sharing a ``seed_family`` lands in the same split. The bucket
    boundaries are ``train`` and ``train + validation``; the remainder is test.
    The assignment is deterministic in ``(seed_family, salt)`` and independent of
    estate order.
    """
    if not 0.0 < train < 1.0 or not 0.0 < validation < 1.0:
        raise ValueError("train and validation fractions must be in (0, 1)")
    if train + validation >= 1.0:
        raise ValueError("train + validation must leave room for a test split")

    val_boundary = train + validation
    train_ids: list[str] = []
    val_ids: list[str] = []
    test_ids: list[str] = []

    # Sort by estate_id for a stable output order regardless of input order.
    for estate in sorted(estates, key=lambda e: e.estate_id):
        bucket = _family_bucket(estate.seed_family, salt)
        if bucket < train:
            train_ids.append(estate.estate_id)
        elif bucket < val_boundary:
            val_ids.append(estate.estate_id)
        else:
            test_ids.append(estate.estate_id)

    return CorpusSplit(
        train=Split("train", tuple(train_ids)),
        validation=Split("validation", tuple(val_ids)),
        test=Split("test", tuple(test_ids)),
    )


def check_split_integrity(estates: Iterable[Estate], split: CorpusSplit) -> None:
    """Raise if the split leaks at the estate or seed-family level.

    Two guarantees, both of which FD-05 §9 requires and reviewers check:

    1. No estate id appears in more than one split.
    2. No seed family spans more than one split.
    """
    buckets = {
        "train": set(split.train.estate_ids),
        "validation": set(split.validation.estate_ids),
        "test": set(split.test.estate_ids),
    }

    # 1. Disjoint estate ids.
    names = list(buckets)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            overlap = buckets[names[i]] & buckets[names[j]]
            if overlap:
                raise ValueError(
                    f"estate id(s) in both {names[i]} and {names[j]}: {sorted(overlap)[:3]}"
                )

    # 2. No family straddles splits.
    estate_to_split: dict[str, str] = {}
    for split_name, ids in buckets.items():
        for estate_id in ids:
            estate_to_split[estate_id] = split_name

    family_to_split: dict[str, str] = {}
    for estate in estates:
        assigned = estate_to_split.get(estate.estate_id)
        if assigned is None:
            raise ValueError(f"estate {estate.estate_id} is missing from the split")
        prior = family_to_split.setdefault(estate.seed_family, assigned)
        if prior != assigned:
            raise ValueError(f"seed family {estate.seed_family!r} straddles {prior} and {assigned}")
