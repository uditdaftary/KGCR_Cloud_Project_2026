"""Parse a ``terraform show -json`` plan into an :class:`EstateGraph`.

This is the FD-08 §5 ETL path: nothing is deployed (FD-05 §10), so the corpus
enters the graph as *plan* output. Resource nodes come from ``planned_values``
(the concrete argument values Terraform computed), and dependency edges come
from ``configuration`` (the ``references`` recorded on each argument
expression). The two sections describe the same resources from different angles;
joining them yields the same graph the internal IR builder produces.

Scope: the root module and nested ``child_modules`` are walked for nodes; edges
are read from the root module's configuration. Module-call boundary edges are a
later refinement (documented, not silently dropped).
"""

from __future__ import annotations

from typing import Any

from kgcr.corpus.graph import Edge, EstateGraph, Node

__all__ = ["parse_plan_json"]


def parse_plan_json(plan: dict[str, Any], *, estate_id: str | None = None) -> EstateGraph:
    """Build an :class:`EstateGraph` from a parsed plan document."""
    graph = EstateGraph(estate_id=estate_id)

    planned = plan.get("planned_values", {})
    root_module = planned.get("root_module", {})
    for resource in _iter_planned_resources(root_module):
        graph.add_node(_node_from_planned(resource))

    known = {n.address for n in graph.nodes}
    config_root = plan.get("configuration", {}).get("root_module", {})
    for edge in _edges_from_configuration(config_root, known):
        graph.add_edge(edge)

    return graph


def _iter_planned_resources(module: dict[str, Any]) -> list[dict[str, Any]]:
    """All managed resources in a module subtree, root first, depth-first."""
    resources: list[dict[str, Any]] = [
        r for r in module.get("resources", []) if r.get("mode", "managed") == "managed"
    ]
    for child in module.get("child_modules", []):
        resources.extend(_iter_planned_resources(child))
    return resources


def _node_from_planned(resource: dict[str, Any]) -> Node:
    return Node(
        address=resource["address"],
        type=resource["type"],
        name=resource["name"],
        attributes=dict(resource.get("values", {})),
    )


def _edges_from_configuration(module: dict[str, Any], known: set[str]) -> list[Edge]:
    edges: list[Edge] = []
    seen: set[tuple[str, str]] = set()

    for resource in module.get("resources", []):
        source = resource.get("address")
        if source is None:
            continue
        for ref in _collect_references(resource.get("expressions", {})):
            target = _resolve_reference(ref, known)
            if target is None or target == source:
                continue
            key = (source, target)
            if key not in seen:
                seen.add(key)
                edges.append(Edge(source=source, target=target))

    return edges


def _collect_references(node: Any) -> list[str]:
    """Recursively gather every ``references`` string in an expressions tree."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "references" and isinstance(value, list):
                found.extend(v for v in value if isinstance(v, str))
            else:
                found.extend(_collect_references(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_references(item))
    return found


def _resolve_reference(ref: str, known: set[str]) -> str | None:
    """Resolve a reference like ``aws_vpc.main.id`` to a known node address.

    Returns the longest dotted prefix of ``ref`` that is a known resource
    address (at least ``type.name``), or ``None`` if it points at something that
    is not a managed resource in this estate (a variable, local, or data source).
    """
    parts = ref.split(".")
    for length in range(len(parts), 1, -1):
        candidate = ".".join(parts[:length])
        if candidate in known:
            return candidate
    return None
