"""Two detection modes — the contrast at the heart of the DF-7 claim.

:func:`single_resource_findings` is a *minimal* stand-in for a single-resource
policy engine (Checkov/CIS): it inspects one resource at a time and flags the
well-known property-level violations. It is deliberately written from the rule
side (the CIS/Checkov semantics named in FD-05 §5), not from the injectors — so
"DF-7 scores zero here" is a real property, not a tautology, and so it returns
**nothing** on the compliant clean corpus.

It is *not* a Checkov replacement. The empirical "single-resource engines score
zero on DF-7" gate runs the real engines in the Phase 4 labelling pipeline
(FD-05 §6); this oracle proves the *by-construction* invariant that no resource
on a DF-7 path is individually non-compliant.

:func:`relational_path_exists` is the other mode: a bounded traversal of the
estate dependency graph. A relational (DF-7) defect is invisible to the first
function and recovered by the second — that gap is the C1 evidence (FD-05 §7).
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.corpus.graph import EstateGraph, build_graph_from_estate
from kgcr.corpus.resources import Resource

__all__ = ["Finding", "single_resource_findings", "relational_path_exists"]


@dataclass(frozen=True, slots=True)
class Finding:
    """One single-resource violation: which resource, which rule, why."""

    address: str
    rule_id: str
    message: str


def single_resource_findings(estate: Estate) -> list[Finding]:
    """Flag property-level violations a single-resource engine would catch.

    One resource is examined at a time — no cross-resource reasoning — mirroring
    what Checkov/Prowler do. Rule ids reference the public rule they stand in
    for. The rule set is intentionally small: it need only cover the
    single-resource defect classes (DF-1…DF-4) and return clean on compliant
    input, which is what makes it a valid oracle for the DF-7 gate.
    """
    findings: list[Finding] = []
    for res in estate.resources:
        findings.extend(_check_resource(res))
    return findings


def _check_resource(res: Resource) -> list[Finding]:
    out: list[Finding] = []
    attrs = res.attributes

    # DF-1 Exposure — security group open to the world on ingress.
    if _has_open_ingress(attrs):
        out.append(Finding(res.address, "CKV_AWS_260", "ingress rule allows 0.0.0.0/0"))

    # DF-1 Exposure — resource reachable from the public internet.
    if attrs.get("publicly_accessible") is True:
        out.append(Finding(res.address, "CKV_AWS_17", "resource is publicly_accessible"))

    # DF-1 Exposure — S3 bucket granted a public ACL.
    acl = attrs.get("acl")
    if isinstance(acl, str) and acl.startswith("public-"):
        out.append(Finding(res.address, "CKV_AWS_20", f"public S3 ACL: {acl}"))

    # DF-2 Encryption — database storage not encrypted at rest.
    if res.type == "aws_db_instance" and attrs.get("storage_encrypted") is not True:
        out.append(Finding(res.address, "CKV_AWS_16", "db storage is not encrypted at rest"))

    # DF-2 Encryption — EBS volume not encrypted.
    if res.type == "aws_ebs_volume" and attrs.get("encrypted") is not True:
        out.append(Finding(res.address, "CKV_AWS_3", "EBS volume is not encrypted"))

    # DF-3 Identity — IAM permission policy grants Action:* on Resource:*.
    if res.type in ("aws_iam_role_policy", "aws_iam_policy") and _is_wildcard_policy(
        attrs.get("policy")
    ):
        out.append(Finding(res.address, "CKV_AWS_1", "IAM policy allows Action:* on Resource:*"))

    # DF-4 Observability — CloudTrail without log-file validation.
    if res.type == "aws_cloudtrail" and attrs.get("enable_log_file_validation") is not True:
        out.append(Finding(res.address, "CKV_AWS_36", "CloudTrail log-file validation disabled"))

    return out


def _has_open_ingress(attrs: dict[str, Any]) -> bool:
    """True if any ingress rule opens 0.0.0.0/0.

    Accepts the two shapes Terraform uses: an ``ingress`` list of rule blocks
    each with ``cidr_blocks``, or a flat ``cidr_blocks`` on the resource.
    """
    ingress = attrs.get("ingress")
    rules = ingress if isinstance(ingress, list) else [attrs]
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        cidrs = rule.get("cidr_blocks")
        if isinstance(cidrs, list) and "0.0.0.0/0" in cidrs:
            return True
    return False


def _is_wildcard_policy(policy: Any) -> bool:
    """True if an IAM policy document allows ``Action:*`` on ``Resource:*``.

    Written to a real engine's semantics: a statement is a finding only when it
    grants the ``*`` action on the ``*`` resource. A scoped resource such as
    ``arn:aws:s3:::kgcr-*/*`` contains a ``*`` but is not ``*`` and must not
    trip — this is why the clean corpus (scoped policies) returns no finding.
    """
    if not isinstance(policy, str):
        return False
    try:
        doc = json.loads(policy)
    except (json.JSONDecodeError, TypeError):
        return False
    statements = doc.get("Statement", []) if isinstance(doc, dict) else []
    if isinstance(statements, dict):
        statements = [statements]
    for stmt in statements:
        if not isinstance(stmt, dict) or stmt.get("Effect") != "Allow":
            continue
        if _wildcards(stmt.get("Action")) and _wildcards(stmt.get("Resource")):
            return True
    return False


def _wildcards(value: Any) -> bool:
    """True if a policy Action/Resource field is exactly ``*`` (scalar or list)."""
    if value == "*":
        return True
    return isinstance(value, list) and "*" in value


def relational_path_exists(
    estate: Estate,
    source: str,
    sink: str,
    *,
    hop_bound: int = 3,
) -> tuple[str, ...] | None:
    """Return a shortest ``source``→``sink`` path within ``hop_bound`` hops, or None.

    Traverses the estate dependency graph as *undirected*: a dependency edge
    means the two resources are connected, and reachability/trust chains run
    along those connections regardless of which side declared the reference.
    ``hop_bound`` is the k of the FD-07 §7 relational predicate (default 3).

    This is the traversal a single-resource engine structurally cannot perform —
    it is what recovers the DF-7 defects that :func:`single_resource_findings`
    cannot see.
    """
    graph = build_graph_from_estate(estate)
    return _shortest_path(graph, source, sink, hop_bound)


def _shortest_path(
    graph: EstateGraph, source: str, sink: str, hop_bound: int
) -> tuple[str, ...] | None:
    if not graph.has_node(source) or not graph.has_node(sink):
        return None

    adjacency: dict[str, set[str]] = {n.address: set() for n in graph.nodes}
    for edge in graph.edges:
        if edge.source in adjacency and edge.target in adjacency:
            adjacency[edge.source].add(edge.target)
            adjacency[edge.target].add(edge.source)

    # BFS gives the shortest hop count; stop once it would exceed the bound.
    queue: deque[tuple[str, ...]] = deque([(source,)])
    seen: set[str] = {source}
    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == sink:
            return path
        if len(path) - 1 >= hop_bound:
            continue
        for neighbour in sorted(adjacency[current]):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append((*path, neighbour))
    return None
