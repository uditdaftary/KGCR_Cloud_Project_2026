"""Will the write role's grant cover this plan? Checked before anything is attempted.

``KGCRProvisionApply`` is granted ``<service>:*`` for each service in the Terraform variable
``provision_services`` (default ``ec2`` and ``s3``) plus ``iam:PassRole``. Applying a plan
with a resource type outside that list would fail partway, leaving half a deployment that
costs money, so the plan is refused up front instead.

``ALLOWED_SERVICES_DEFAULT`` mirrors the Terraform default; a test parses
``src/aws/variables.tf`` and fails if the two drift. A deliberately widened role is
declared to the CLI with ``KGCR_PROVISION_SERVICES``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

__all__ = ["ALLOWED_SERVICES_DEFAULT", "allowed_services", "check", "service_for"]

ALLOWED_SERVICES_DEFAULT: tuple[str, ...] = ("ec2", "s3")

# The IAM service prefix whose actions create each Terraform resource type.
_SERVICE: dict[str, str] = {
    "aws_vpc": "ec2",
    "aws_subnet": "ec2",
    "aws_security_group": "ec2",
    "aws_internet_gateway": "ec2",
    "aws_nat_gateway": "ec2",
    "aws_instance": "ec2",
    "aws_s3_bucket": "s3",
    "aws_s3_bucket_server_side_encryption_configuration": "s3",
    "aws_db_instance": "rds",
    "aws_db_subnet_group": "rds",
    "aws_kms_key": "kms",
    "aws_lb": "elasticloadbalancing",
    "aws_iam_role": "iam",
    "aws_iam_role_policy": "iam",
    "aws_cloudtrail": "cloudtrail",
    "aws_glue_catalog_database": "glue",
}


def service_for(resource_type: str) -> str:
    """The service prefix for ``resource_type``; ``KeyError`` for a type not mapped."""
    return _SERVICE[resource_type]


def allowed_services(env: Mapping[str, str]) -> tuple[str, ...]:
    """The services the role is declared to grant: the shipped default unless widened."""
    declared = env.get("KGCR_PROVISION_SERVICES", "").strip()
    if not declared:
        return ALLOWED_SERVICES_DEFAULT
    return tuple(sorted({s.strip().lower() for s in declared.split(",") if s.strip()}))


def check(types: Iterable[str], allowed: Iterable[str]) -> list[str]:
    """Resource types the grant does not cover, with the service each needs."""
    granted = set(allowed)
    offenders: list[str] = []
    for res_type in sorted(set(types)):
        try:
            service = service_for(res_type)
        except KeyError:
            offenders.append(f"{res_type} (service unknown to the preflight)")
            continue
        if service not in granted:
            offenders.append(f"{res_type} (needs {service})")
    return offenders
