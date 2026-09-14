"""Defect injectors: mutate a clean estate, record per-defect ground truth.

Each injector takes a clean :class:`~kgcr.corpus.estate.Estate` and returns a
:class:`DefectedEstate` — a new, frozen estate with a *distinct* id (derived
from the parent id and the variant, so a defect estate never collides with its
parent) paired with the :class:`~kgcr.defects.taxonomy.DefectInstance` ground
truth. Injection is a pure function of the parent estate, so the whole defect
corpus reproduces from the clean corpus seeds.

Two families:

* **DF-1…DF-6** set a property-level violation on a single resource. A
  single-resource engine catches these (DF-1…DF-4 fully; DF-5/DF-6 partly).
* **DF-7** adds *individually-compliant* resources and wires them into a
  bounded path through the graph — internet→data reachability, a transitive
  trust chain, a privilege-escalation hop. No resource on the path is
  individually non-compliant; the defect exists only in the composition. This
  is the class single-resource engines cannot reach (FD-05 §5, §7).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from kgcr.corpus.estate import Estate
from kgcr.corpus.resources import Resource
from kgcr.defects.taxonomy import (
    DEFAULT_CONTROL,
    DEFAULT_SEVERITY,
    DefectClass,
    DefectInstance,
    Severity,
)
from kgcr.hashing import canonical_hash

__all__ = ["DefectedEstate", "Injector", "INJECTORS", "applicable_injectors"]


@dataclass(frozen=True, slots=True)
class DefectedEstate:
    """An injected estate and its ground-truth record."""

    estate: Estate
    defect: DefectInstance


@dataclass(frozen=True, slots=True)
class Injector:
    """One defect variant: whether it applies to an estate, and how to inject it."""

    variant: str
    defect_class: DefectClass
    applies: Callable[[Estate], bool]
    run: Callable[[Estate], DefectedEstate]


# --- estate rebuild helpers --------------------------------------------------


def _new_estate_id(parent: Estate, variant: str) -> str:
    """A stable id for the injected estate, distinct from the parent's."""
    return canonical_hash({"parent": parent.estate_id, "variant": variant})[:16]


def _rebuild(parent: Estate, resources: tuple[Resource, ...], variant: str) -> Estate:
    """Rebuild the estate with new resources, preserving intent and seed family.

    ``seed_family`` is preserved so the estate-level split (FD-05 §9) keeps the
    injected estate on the same side of the train/test boundary as its clean
    parent — a defect estate and its parent must never straddle the split.
    """
    return Estate(
        estate_id=_new_estate_id(parent, variant),
        intent=parent.intent,
        resources=resources,
        seed=parent.seed,
        seed_family=parent.seed_family,
        region=parent.region,
    )


def _replace_resource(estate: Estate, updated: Resource) -> tuple[Resource, ...]:
    """Return the resource tuple with the resource at ``updated.address`` swapped."""
    return tuple(updated if r.address == updated.address else r for r in estate.resources)


def _emit(
    parent: Estate,
    resources: tuple[Resource, ...],
    *,
    defect_class: DefectClass,
    variant: str,
    injection_site: tuple[str, ...],
    expected_finding: str,
    control: str | None = None,
    severity: Severity | None = None,
    evidence_path: tuple[str, ...] = (),
) -> DefectedEstate:
    estate = _rebuild(parent, resources, variant)
    defect = DefectInstance(
        defect_class=defect_class,
        variant=variant,
        estate_id=estate.estate_id,
        parent_estate_id=parent.estate_id,
        seed_family=parent.seed_family,
        control=control if control is not None else DEFAULT_CONTROL[defect_class],
        severity=severity if severity is not None else DEFAULT_SEVERITY[defect_class],
        injection_site=injection_site,
        expected_finding=expected_finding,
        evidence_path=evidence_path,
    )
    return DefectedEstate(estate=estate, defect=defect)


# --- estate query helpers ----------------------------------------------------


def _addresses(estate: Estate) -> set[str]:
    return set(estate.resource_addresses)


def _get(estate: Estate, address: str) -> Resource | None:
    return next((r for r in estate.resources if r.address == address), None)


def _public_subnet(estate: Estate) -> str | None:
    for res in estate.resources:
        if res.type == "aws_subnet" and res.attributes.get("map_public_ip_on_launch") is True:
            return res.address
    return None


# The sink for a relational defect must be a genuinely sensitive data store —
# cardholder data or PII. A path to a low-sensitivity store (e.g. the logs
# bucket) is not the CRITICAL PCI breach DF-7 represents, and FD-05 §3 makes the
# internal_reporting archetype the low-sensitivity *contrast* case that must not
# accumulate CRITICAL controls. So DF-7 is injected only where such a store
# exists (payments, customer-data), never on reporting estates.
_SENSITIVE_SINKS = (
    "aws_db_instance.cardholder",  # cardholder data (payments)
    "aws_s3_bucket.lake",  # PII data lake (customer-data)
    "aws_glue_catalog_database.pii",  # PII catalogue (customer-data)
)


def _sensitive_sink(estate: Estate) -> str | None:
    """The most sensitive data store present, or None if the estate has none."""
    present = _addresses(estate)
    for address in _SENSITIVE_SINKS:
        if address in present:
            return address
    return None


# --- DF-1…DF-6: single-resource property defects -----------------------------


def _df1_open_security_group(estate: Estate) -> DefectedEstate:
    sg = _get(estate, "aws_security_group.app")
    assert sg is not None  # guarded by `applies`
    opened = replace(
        sg,
        attributes={
            **sg.attributes,
            "ingress": [
                {
                    "from_port": 443,
                    "to_port": 443,
                    "protocol": "tcp",
                    "cidr_blocks": ["0.0.0.0/0"],
                }
            ],
        },
    )
    return _emit(
        estate,
        _replace_resource(estate, opened),
        defect_class=DefectClass.EXPOSURE,
        variant="open_security_group",
        injection_site=("aws_security_group.app",),
        expected_finding="security group aws_security_group.app permits ingress from 0.0.0.0/0",
    )


def _df2_unencrypted_database(estate: Estate) -> DefectedEstate:
    db = _get(estate, "aws_db_instance.cardholder")
    assert db is not None
    plain = replace(db, attributes={**db.attributes, "storage_encrypted": False})
    return _emit(
        estate,
        _replace_resource(estate, plain),
        defect_class=DefectClass.ENCRYPTION,
        variant="unencrypted_database",
        injection_site=("aws_db_instance.cardholder",),
        expected_finding="cardholder database storage is not encrypted at rest (PCI-DSS 3.4)",
    )


def _df3_wildcard_iam_policy(estate: Estate) -> DefectedEstate:
    policy = _get(estate, "aws_iam_role_policy.app")
    assert policy is not None
    wild = replace(
        policy,
        attributes={
            **policy.attributes,
            "policy": '{"Version":"2012-10-17","Statement":'
            '[{"Effect":"Allow","Action":"*","Resource":"*"}]}',
        },
    )
    return _emit(
        estate,
        _replace_resource(estate, wild),
        defect_class=DefectClass.IDENTITY,
        variant="wildcard_iam_policy",
        injection_site=("aws_iam_role_policy.app",),
        expected_finding="IAM policy grants Action:* on Resource:* (violates least privilege)",
    )


def _df4_cloudtrail_no_validation(estate: Estate) -> DefectedEstate:
    trail = _get(estate, "aws_cloudtrail.trail")
    assert trail is not None
    weakened = replace(trail, attributes={**trail.attributes, "enable_log_file_validation": False})
    return _emit(
        estate,
        _replace_resource(estate, weakened),
        defect_class=DefectClass.OBSERVABILITY,
        variant="cloudtrail_no_log_validation",
        injection_site=("aws_cloudtrail.trail",),
        expected_finding="CloudTrail log-file validation disabled (CIS AWS 3.2)",
    )


def _df5_no_database_backup(estate: Estate) -> DefectedEstate:
    db = _get(estate, "aws_db_instance.cardholder")
    assert db is not None
    fragile = replace(
        db,
        attributes={**db.attributes, "backup_retention_period": 0, "multi_az": False},
    )
    return _emit(
        estate,
        _replace_resource(estate, fragile),
        defect_class=DefectClass.RESILIENCE,
        variant="no_database_backup",
        injection_site=("aws_db_instance.cardholder",),
        expected_finding="database has no backup retention and is single-AZ (resilience gap)",
    )


def _df6_unattached_volume(estate: Estate) -> DefectedEstate:
    # An encrypted (so this is not also an encryption defect) but unattached
    # volume: cost with no workload. Added, not mutated.
    orphan = Resource(
        "aws_ebs_volume",
        "df6_orphan",
        {"availability_zone": f"{estate.region}a", "size": 100, "encrypted": True},
    )
    return _emit(
        estate,
        (*estate.resources, orphan),
        defect_class=DefectClass.COST,
        variant="unattached_volume",
        injection_site=("aws_ebs_volume.df6_orphan",),
        expected_finding="unattached EBS volume incurs cost with no attached workload",
    )


# --- DF-7: relational path defects (the headline) ----------------------------
#
# Each adds only individually-compliant resources and wires them into a path of
# length <= 3 through the graph. The evidence_path is recorded so the seeded
# recall metric can check that a graph traversal recovers exactly this path,
# while a single-resource engine sees nothing.


def _df7a_internet_reachability(estate: Estate) -> DefectedEstate:
    subnet = _public_subnet(estate)
    sink = _sensitive_sink(estate)
    assert subnet is not None and sink is not None  # guarded by `applies`
    igw = "aws_internet_gateway.igw"

    # Public subnet gains a default route to the internet gateway (the edge that
    # makes it genuinely public). Compliant on its own — routing is not a
    # single-resource finding.
    subnet_res = _get(estate, subnet)
    assert subnet_res is not None
    routed = replace(subnet_res, references=(*subnet_res.references, igw))

    # A host in the public subnet that also connects to the sensitive store.
    # Nothing about this instance is individually non-compliant.
    hop = Resource(
        "aws_instance",
        "df7_public_hop",
        {"instance_type": "t3.small", "__ref__subnet_id": subnet, "tags": {"Name": "df7-hop"}},
        references=(subnet, sink),
    )
    resources = (*_replace_resource(estate, routed), hop)
    hop_address = "aws_instance.df7_public_hop"
    return _emit(
        estate,
        resources,
        defect_class=DefectClass.RELATIONAL,
        variant="indirect_internet_reachability",
        control="kg://control/pci-dss-v4/1.3",
        injection_site=(hop_address, subnet),
        expected_finding=(
            f"internet-reachable path to {sink} within 3 hops via a public-subnet host; "
            "no resource on the path is individually public"
        ),
        evidence_path=(igw, subnet, hop_address, sink),
    )


def _df7b_transitive_trust_chain(estate: Estate) -> DefectedEstate:
    sink = _sensitive_sink(estate)
    assert sink is not None  # guarded by `applies`
    a = Resource(
        "aws_iam_role",
        "df7_trust_a",
        {"name": "df7-trust-a", "assume_role_policy": _assume_service("ec2.amazonaws.com")},
    )
    b = Resource(
        "aws_iam_role",
        "df7_trust_b",
        {"name": "df7-trust-b", "assume_role_policy": _assume_role("df7-trust-a")},
        references=("aws_iam_role.df7_trust_a",),
    )
    # Terminal role trusts the middle role and reaches the sensitive store.
    c = Resource(
        "aws_iam_role",
        "df7_trust_c",
        {"name": "df7-trust-c", "assume_role_policy": _assume_role("df7-trust-b")},
        references=("aws_iam_role.df7_trust_b", sink),
    )
    return _emit(
        estate,
        (*estate.resources, a, b, c),
        defect_class=DefectClass.RELATIONAL,
        variant="transitive_trust_chain",
        control="kg://control/pci-dss-v4/7.2",
        injection_site=(a.address, b.address, c.address),
        expected_finding=(
            f"transitive assume-role chain {a.address}→{b.address}→{c.address} reaches {sink}; "
            "no single role is over-privileged"
        ),
        evidence_path=(a.address, b.address, c.address, sink),
    )


def _df7c_privilege_escalation(estate: Estate) -> DefectedEstate:
    sink = _sensitive_sink(estate)
    assert sink is not None  # guarded by `applies`
    priv = Resource(
        "aws_iam_role",
        "df7_priv",
        {"name": "df7-priv", "assume_role_policy": _assume_service("ec2.amazonaws.com")},
        references=(sink,),
    )
    # Execution role that can pass/assume the privileged role (iam:PassRole).
    # The escalation is carried structurally by the reference edge to df7_priv,
    # not by any attribute — the role uses only real arguments so it still
    # renders to valid Terraform for the plan-based labelling engines (P4). The
    # capability is only visible as the two-hop path to the sink.
    exec_role = Resource(
        "aws_iam_role",
        "df7_exec",
        {
            "name": "df7-exec",
            "assume_role_policy": _assume_service("lambda.amazonaws.com"),
        },
        references=("aws_iam_role.df7_priv",),
    )
    return _emit(
        estate,
        (*estate.resources, priv, exec_role),
        defect_class=DefectClass.RELATIONAL,
        variant="privilege_escalation_passrole",
        control="kg://control/pci-dss-v4/7.2",
        injection_site=(exec_role.address, priv.address),
        expected_finding=(
            f"privilege-escalation path: {exec_role.address} may pass/assume {priv.address} "
            f"which reaches {sink}"
        ),
        evidence_path=(exec_role.address, priv.address, sink),
    )


def _assume_service(service: str) -> str:
    return (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
        f'"Principal":{{"Service":"{service}"}},"Action":"sts:AssumeRole"}}]}}'
    )


def _assume_role(role_name: str) -> str:
    return (
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
        f'"Principal":{{"AWS":"role/{role_name}"}},"Action":"sts:AssumeRole"}}]}}'
    )


# --- registry ----------------------------------------------------------------


def _has(address: str) -> Callable[[Estate], bool]:
    return lambda estate: address in _addresses(estate)


def _has_sensitive_sink(estate: Estate) -> bool:
    return _sensitive_sink(estate) is not None


def _df7a_applies(estate: Estate) -> bool:
    return (
        "aws_internet_gateway.igw" in _addresses(estate)
        and _public_subnet(estate) is not None
        and _has_sensitive_sink(estate)
    )


_ALWAYS: Callable[[Estate], bool] = lambda _e: True  # noqa: E731

INJECTORS: tuple[Injector, ...] = (
    Injector(
        "open_security_group",
        DefectClass.EXPOSURE,
        _has("aws_security_group.app"),
        _df1_open_security_group,
    ),
    Injector(
        "unencrypted_database",
        DefectClass.ENCRYPTION,
        _has("aws_db_instance.cardholder"),
        _df2_unencrypted_database,
    ),
    Injector(
        "wildcard_iam_policy",
        DefectClass.IDENTITY,
        _has("aws_iam_role_policy.app"),
        _df3_wildcard_iam_policy,
    ),
    Injector(
        "cloudtrail_no_log_validation",
        DefectClass.OBSERVABILITY,
        _has("aws_cloudtrail.trail"),
        _df4_cloudtrail_no_validation,
    ),
    Injector(
        "no_database_backup",
        DefectClass.RESILIENCE,
        _has("aws_db_instance.cardholder"),
        _df5_no_database_backup,
    ),
    Injector("unattached_volume", DefectClass.COST, _ALWAYS, _df6_unattached_volume),
    Injector(
        "indirect_internet_reachability",
        DefectClass.RELATIONAL,
        _df7a_applies,
        _df7a_internet_reachability,
    ),
    Injector(
        "transitive_trust_chain",
        DefectClass.RELATIONAL,
        _has_sensitive_sink,
        _df7b_transitive_trust_chain,
    ),
    Injector(
        "privilege_escalation_passrole",
        DefectClass.RELATIONAL,
        _has_sensitive_sink,
        _df7c_privilege_escalation,
    ),
)


def applicable_injectors(estate: Estate) -> list[Injector]:
    """The injectors whose defect can be injected into ``estate``."""
    return [inj for inj in INJECTORS if inj.applies(estate)]
