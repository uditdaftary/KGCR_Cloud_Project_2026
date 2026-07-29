"""Render an :class:`~kgcr.corpus.estate.Estate` from an
:class:`~kgcr.corpus.intent.Intent`.

This is the intent-*first* step of FD-05 §4A: the intent already exists, and the
generator's job is to lay down a plausible, *clean* AWS estate that serves it.
The output is deterministic in ``(intent, seed)`` — the same pair always yields
byte-identical resources — which is what makes the corpus reproducible and the
estate-level split by seed family meaningful.

The estate is compliant by construction here; defect injection (Phase 5)
operates on the rendered resources afterwards. The resources are real
``aws_*`` types with real arguments so the same output feeds ``terraform plan``,
the Phase 4 policy engines, and the graph builder without translation.
"""

from __future__ import annotations

import random

from kgcr.corpus.estate import Estate
from kgcr.corpus.intent import (
    Archetype,
    AZSpread,
    Intent,
    LoggingPosture,
    NetworkLayout,
    Scale,
)
from kgcr.corpus.resources import Resource
from kgcr.hashing import canonical_hash
from kgcr.repro import DEFAULT_SEED

__all__ = ["render_estate", "estate_id_for"]

_AZ_COUNT: dict[AZSpread, int] = {
    AZSpread.SINGLE_AZ: 1,
    AZSpread.TWO_AZ: 2,
    AZSpread.THREE_AZ: 3,
}

_INSTANCE_CLASS: dict[Scale, str] = {
    Scale.SMALL: "t3.small",
    Scale.MEDIUM: "m5.large",
    Scale.LARGE: "m5.2xlarge",
}

_DB_CLASS: dict[Scale, str] = {
    Scale.SMALL: "db.t3.small",
    Scale.MEDIUM: "db.m5.large",
    Scale.LARGE: "db.m5.2xlarge",
}


def estate_id_for(intent: Intent, seed: int) -> str:
    """Deterministic estate id from the intent identity and the seed."""
    return canonical_hash({"intent": intent.intent_hash, "seed": seed})[:16]


def render_estate(
    intent: Intent,
    seed: int = DEFAULT_SEED,
    *,
    seed_family: str | None = None,
) -> Estate:
    """Render a clean estate for ``intent``.

    ``seed`` drives any within-estate variation (currently CIDR/name jitter)
    deterministically. ``seed_family`` groups estates that must not straddle a
    train/test split; it defaults to the estate's own id (each estate its own
    family).
    """
    rng = random.Random(seed)
    builder = _EstateBuilder(intent, rng)
    builder.build()

    estate_id = estate_id_for(intent, seed)
    return Estate(
        estate_id=estate_id,
        intent=intent,
        resources=tuple(builder.resources),
        seed=seed,
        seed_family=seed_family if seed_family is not None else estate_id,
        region=intent.region,
    )


class _EstateBuilder:
    """Accumulates the resources for one estate; order is deterministic."""

    def __init__(self, intent: Intent, rng: random.Random) -> None:
        self.intent = intent
        self.rng = rng
        self.resources: list[Resource] = []
        self._second_octet = rng.randint(0, 240)

    # --- public build --------------------------------------------------------

    def build(self) -> None:
        self._network()
        self._encryption_key()
        self._logging()
        self._workload_identity()
        self._archetype_resources()

    # --- shared helpers ------------------------------------------------------

    def _tags(self, name: str) -> dict[str, str]:
        base = {"Name": name}
        # Tagging discipline is legitimate variation, not a defect.
        if self.intent.tagging.value == "strict":
            base.update(
                {
                    "project": "kgcr",
                    "archetype": self.intent.archetype.value,
                    "data_sensitivity": self.intent.data_sensitivity,
                    "owner": "platform",
                }
            )
        elif self.intent.tagging.value == "partial":
            base["project"] = "kgcr"
        return base

    def _cidr(self, subnet_index: int) -> str:
        return f"10.{self._second_octet}.{subnet_index}.0/24"

    def _add(self, resource: Resource) -> None:
        self.resources.append(resource)

    # --- building blocks -----------------------------------------------------

    def _network(self) -> None:
        self._add(
            Resource(
                "aws_vpc",
                "main",
                {"cidr_block": f"10.{self._second_octet}.0.0/16", "tags": self._tags("main")},
            )
        )

        layout = self.intent.network_layout
        az_count = _AZ_COUNT[self.intent.az_spread]
        has_public = layout in (NetworkLayout.PUBLIC_ONLY, NetworkLayout.PUBLIC_PRIVATE)
        has_private = layout in (
            NetworkLayout.PUBLIC_PRIVATE,
            NetworkLayout.PRIVATE_WITH_NAT,
        )

        if has_public:
            self._add(
                Resource(
                    "aws_internet_gateway",
                    "igw",
                    {"__ref__vpc_id": "aws_vpc.main", "tags": self._tags("igw")},
                    references=("aws_vpc.main",),
                )
            )

        index = 1
        for az in range(az_count):
            if has_public:
                self._add(
                    Resource(
                        "aws_subnet",
                        f"public_{az}",
                        {
                            "__ref__vpc_id": "aws_vpc.main",
                            "cidr_block": self._cidr(index),
                            "map_public_ip_on_launch": True,
                            "tags": self._tags(f"public-{az}"),
                        },
                        references=("aws_vpc.main",),
                    )
                )
                index += 1
            if has_private:
                self._add(
                    Resource(
                        "aws_subnet",
                        f"private_{az}",
                        {
                            "__ref__vpc_id": "aws_vpc.main",
                            "cidr_block": self._cidr(index),
                            "map_public_ip_on_launch": False,
                            "tags": self._tags(f"private-{az}"),
                        },
                        references=("aws_vpc.main",),
                    )
                )
                index += 1

        if layout is NetworkLayout.PRIVATE_WITH_NAT and has_public:
            self._add(
                Resource(
                    "aws_nat_gateway",
                    "nat",
                    {"__ref__subnet_id": "aws_subnet.public_0", "tags": self._tags("nat")},
                    references=("aws_subnet.public_0", "aws_internet_gateway.igw"),
                )
            )

        self._add(
            Resource(
                "aws_security_group",
                "app",
                {
                    "__ref__vpc_id": "aws_vpc.main",
                    "description": "application security group",
                    "tags": self._tags("app-sg"),
                },
                references=("aws_vpc.main",),
            )
        )

    def _encryption_key(self) -> None:
        # Clean corpus: a customer-managed key is always present and used.
        self._add(
            Resource(
                "aws_kms_key",
                "main",
                {
                    "description": "estate data key",
                    "enable_key_rotation": True,
                    "tags": self._tags("kms"),
                },
            )
        )

    def _logging(self) -> None:
        self._add(
            Resource(
                "aws_s3_bucket",
                "logs",
                {"bucket_prefix": "kgcr-logs-", "tags": self._tags("logs")},
            )
        )
        self._add(
            Resource(
                "aws_s3_bucket_server_side_encryption_configuration",
                "logs",
                {"__ref__bucket": "aws_s3_bucket.logs"},
                references=("aws_s3_bucket.logs",),
            )
        )
        if self.intent.logging is LoggingPosture.FULL:
            self._add(
                Resource(
                    "aws_cloudtrail",
                    "trail",
                    {
                        "name": "kgcr-trail",
                        "__ref__s3_bucket_name": "aws_s3_bucket.logs",
                        "is_multi_region_trail": True,
                        "enable_log_file_validation": True,
                        "tags": self._tags("trail"),
                    },
                    references=("aws_s3_bucket.logs",),
                )
            )

    def _workload_identity(self) -> None:
        self._add(
            Resource(
                "aws_iam_role",
                "app",
                {
                    "name": "kgcr-app-role",
                    "assume_role_policy": _ASSUME_EC2,
                    "tags": self._tags("app-role"),
                },
            )
        )
        # Least-privilege vs role-per-service is legitimate IAM-shape variation;
        # both are clean (no wildcard actions — that is a Phase 5 DF-3 defect).
        self._add(
            Resource(
                "aws_iam_role_policy",
                "app",
                {
                    "name": "kgcr-app-policy",
                    "__ref__role": "aws_iam_role.app",
                    "policy": _SCOPED_S3_POLICY,
                },
                references=("aws_iam_role.app",),
            )
        )

    def _archetype_resources(self) -> None:
        dispatch = {
            Archetype.PAYMENTS_API: self._payments,
            Archetype.CUSTOMER_DATA_PLATFORM: self._customer_data,
            Archetype.INTERNAL_REPORTING: self._reporting,
        }
        dispatch[self.intent.archetype]()

    def _payments(self) -> None:
        self._add(
            Resource(
                "aws_db_instance",
                "cardholder",
                {
                    "identifier": "kgcr-cardholder",
                    "engine": "postgres",
                    "instance_class": _DB_CLASS[self.intent.scale],
                    "allocated_storage": 20,
                    "storage_encrypted": True,
                    "__ref__kms_key_id": "aws_kms_key.main",
                    "publicly_accessible": False,
                    "tags": self._tags("cardholder-db"),
                },
                references=("aws_kms_key.main",),
            )
        )
        self._add(
            Resource(
                "aws_lb",
                "api",
                {
                    "name": "kgcr-api-lb",
                    "internal": self.intent.network_layout is NetworkLayout.PRIVATE_WITH_NAT,
                    "load_balancer_type": "application",
                    "tags": self._tags("api-lb"),
                },
                references=("aws_security_group.app",),
            )
        )

    def _customer_data(self) -> None:
        self._add(
            Resource(
                "aws_s3_bucket",
                "lake",
                {"bucket_prefix": "kgcr-lake-", "tags": self._tags("data-lake")},
            )
        )
        self._add(
            Resource(
                "aws_s3_bucket_server_side_encryption_configuration",
                "lake",
                # bucket is a real argument; the KMS key participates through the
                # nested rule block, so it is expressed as a dependency edge
                # rather than a top-level argument.
                {"__ref__bucket": "aws_s3_bucket.lake"},
                references=("aws_s3_bucket.lake", "aws_kms_key.main"),
            )
        )
        self._add(
            Resource(
                "aws_glue_catalog_database",
                "pii",
                {"name": "kgcr_pii_catalog", "tags": self._tags("pii-catalog")},
            )
        )

    def _reporting(self) -> None:
        # Cost-dominant contrast case: a single compute instance, sized by scale.
        self._add(
            Resource(
                "aws_instance",
                "reporting",
                {
                    "instance_type": _INSTANCE_CLASS[self.intent.scale],
                    "__ref__subnet_id": self._reporting_subnet(),
                    # security groups are a list argument; carried as a
                    # dependency edge rather than a scalar interpolation.
                    "tags": self._tags("reporting"),
                },
                references=(self._reporting_subnet(), "aws_security_group.app"),
            )
        )

    def _reporting_subnet(self) -> str:
        addresses = {r.address for r in self.resources}
        for candidate in ("aws_subnet.private_0", "aws_subnet.public_0"):
            if candidate in addresses:
                return candidate
        return "aws_vpc.main"


_ASSUME_EC2 = (
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
    '"Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
)

_SCOPED_S3_POLICY = (
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
    '"Action":["s3:GetObject","s3:PutObject"],'
    '"Resource":"arn:aws:s3:::kgcr-*/*"}]}'
)
