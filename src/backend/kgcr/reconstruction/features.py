"""Structural features of an estate — the reconstructor's only input.

Every feature is a function of the estate's *resources and topology*, never of
its :class:`~kgcr.corpus.intent.Intent`. That separation is the FD-05 §8
discipline made structural: the reconstructor sees what a harvested account would
expose, not the intent it must recover. :func:`extract_features` deliberately
does not read ``estate.intent``.

The feature set is chosen to expose the signal each intent axis leaves in the
topology: archetype from its signature resources, network layout from the
gateway/subnet mix, scale from instance sizing, tagging from tag richness. One
axis — ``iam_shape`` — leaves *no* structural trace in the current generator, and
that is intentional: the reconstructor should be visibly unconfident about it,
which is exactly what the calibration evaluation checks.
"""

from __future__ import annotations

from kgcr.corpus.estate import Estate

__all__ = ["FEATURE_NAMES", "extract_features", "feature_vector"]

# Ordinal ranks for instance sizing (the scale axis signal).
_SIZE_RANK: dict[str, int] = {
    "t3.small": 0,
    "m5.large": 1,
    "m5.2xlarge": 2,
    "db.t3.small": 0,
    "db.m5.large": 1,
    "db.m5.2xlarge": 2,
}

FEATURE_NAMES: tuple[str, ...] = (
    "n_resources",
    "n_subnets",
    "n_public_subnets",
    "n_private_subnets",
    "az_count_estimate",
    "has_igw",
    "has_nat",
    "has_cloudtrail",
    "has_cardholder_db",
    "has_glue_pii",
    "has_lake",
    "has_reporting_instance",
    "has_lb",
    "n_iam_roles",
    "n_iam_policies",
    "max_tag_keys",
    "instance_size_rank",
)


def extract_features(estate: Estate) -> dict[str, float]:
    """Structural feature dict for ``estate`` (reads resources only)."""
    by_type: dict[str, int] = {}
    n_public = 0
    n_private = 0
    max_tag_keys = 0
    size_rank = 0

    for res in estate.resources:
        by_type[res.type] = by_type.get(res.type, 0) + 1

        if res.type == "aws_subnet":
            if res.attributes.get("map_public_ip_on_launch") is True:
                n_public += 1
            else:
                n_private += 1

        tags = res.attributes.get("tags")
        if isinstance(tags, dict):
            max_tag_keys = max(max_tag_keys, len(tags))

        size_rank = max(size_rank, _size_rank_of(res.type, res.attributes))

    def has(address_type: str) -> float:
        return 1.0 if by_type.get(address_type, 0) > 0 else 0.0

    return {
        "n_resources": float(len(estate.resources)),
        "n_subnets": float(by_type.get("aws_subnet", 0)),
        "n_public_subnets": float(n_public),
        "n_private_subnets": float(n_private),
        "az_count_estimate": float(max(n_public, n_private)),
        "has_igw": has("aws_internet_gateway"),
        "has_nat": has("aws_nat_gateway"),
        "has_cloudtrail": has("aws_cloudtrail"),
        "has_cardholder_db": _has_named(estate, "aws_db_instance", "cardholder"),
        "has_glue_pii": _has_named(estate, "aws_glue_catalog_database", "pii"),
        "has_lake": _has_named(estate, "aws_s3_bucket", "lake"),
        "has_reporting_instance": _has_named(estate, "aws_instance", "reporting"),
        "has_lb": has("aws_lb"),
        "n_iam_roles": float(by_type.get("aws_iam_role", 0)),
        "n_iam_policies": float(by_type.get("aws_iam_role_policy", 0)),
        "max_tag_keys": float(max_tag_keys),
        "instance_size_rank": float(size_rank),
    }


def feature_vector(estate: Estate) -> list[float]:
    """The feature dict as a vector in :data:`FEATURE_NAMES` order."""
    features = extract_features(estate)
    return [features[name] for name in FEATURE_NAMES]


def _size_rank_of(res_type: str, attributes: dict[str, object]) -> int:
    if res_type == "aws_instance":
        return _SIZE_RANK.get(str(attributes.get("instance_type", "")), 0)
    if res_type == "aws_db_instance":
        return _SIZE_RANK.get(str(attributes.get("instance_class", "")), 0)
    return 0


def _has_named(estate: Estate, res_type: str, name: str) -> float:
    address = f"{res_type}.{name}"
    return 1.0 if address in estate.resource_addresses else 0.0
