"""The observed-estate graph (L2) as an in-memory structure.

FD-08 §5 loads the observed layer into Neo4j; that host is not available during
development, so :class:`EstateGraph` is a lightweight, serialisable stand-in
with the same shape — typed resource nodes and directed dependency edges — that
loads into Neo4j unchanged when the host exists.

Two builders produce it:

* :func:`build_graph_from_estate` — from the internal estate IR (works now, no
  terraform required).
* :func:`~kgcr.corpus.plan_parser.parse_plan_json` — from a real
  ``terraform show -json`` plan (the path used once terraform is available).

Both emit the same graph, so downstream phases never care which produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kgcr.corpus.estate import Estate

__all__ = ["Node", "Edge", "EstateGraph", "build_graph_from_estate", "DEPENDS_ON"]

# The single edge relation at this layer: "this resource references that one".
DEPENDS_ON = "DEPENDS_ON"


@dataclass(frozen=True, slots=True)
class Node:
    """A resource node, addressed ``type.name``."""

    address: str
    type: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Edge:
    """A directed dependency edge, ``source`` -> ``target``."""

    source: str
    target: str
    relation: str = DEPENDS_ON


class EstateGraph:
    """A directed graph of resources and their dependencies."""

    def __init__(self, estate_id: str | None = None) -> None:
        self.estate_id = estate_id
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []

    # --- construction --------------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.address in self._nodes:
            raise ValueError(f"duplicate node address: {node.address}")
        self._nodes[node.address] = node

    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)

    # --- access --------------------------------------------------------------

    @property
    def nodes(self) -> list[Node]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def has_node(self, address: str) -> bool:
        return address in self._nodes

    def node(self, address: str) -> Node:
        return self._nodes[address]

    def neighbours(self, address: str) -> list[str]:
        """Addresses this node depends on (outgoing edges)."""
        return [e.target for e in self._edges if e.source == address]

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # --- integrity -----------------------------------------------------------

    def dangling_edges(self) -> list[Edge]:
        """Edges whose source or target is not a known node."""
        return [
            e for e in self._edges if e.source not in self._nodes or e.target not in self._nodes
        ]

    def validate(self) -> None:
        """Raise if any edge references a missing node."""
        dangling = self.dangling_edges()
        if dangling:
            raise ValueError(f"graph has {len(dangling)} dangling edge(s): {dangling[:3]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "estate_id": self.estate_id,
            "nodes": [
                {
                    "address": n.address,
                    "type": n.type,
                    "name": n.name,
                    "attributes": dict(n.attributes),
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "relation": e.relation}
                for e in self._edges
            ],
        }


def build_graph_from_estate(estate: Estate) -> EstateGraph:
    """Build the dependency graph directly from an estate's IR.

    Nodes carry the resource attributes with the internal ``__ref__`` markers
    stripped (those are rendering hints, not real attributes). Edges come from
    each resource's ``references``; a reference to a resource not in the estate
    is skipped rather than producing a dangling edge.
    """
    graph = EstateGraph(estate_id=estate.estate_id)
    addresses = set(estate.resource_addresses)

    for res in estate.resources:
        clean_attrs = {k: v for k, v in res.attributes.items() if not k.startswith("__ref__")}
        graph.add_node(
            Node(address=res.address, type=res.type, name=res.name, attributes=clean_attrs)
        )

    for res in estate.resources:
        for ref in res.references:
            if ref in addresses:
                graph.add_edge(Edge(source=res.address, target=ref))

    return graph
