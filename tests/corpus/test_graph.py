"""The estate graph builder produces a clean, consistent dependency graph."""

from __future__ import annotations

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.corpus.graph import DEPENDS_ON, Edge, EstateGraph, Node, build_graph_from_estate
from kgcr.corpus.intent import Archetype
from kgcr.corpus.sampler import IntentSampler


def test_graph_has_one_node_per_resource() -> None:
    estate = render_estate(IntentSampler(1).sample(), 1)
    graph = build_graph_from_estate(estate)
    assert graph.node_count == len(estate.resources)
    assert {n.address for n in graph.nodes} == set(estate.resource_addresses)


def test_graph_has_no_dangling_edges() -> None:
    for seed in range(15):
        estate = render_estate(IntentSampler(seed).sample(), seed)
        graph = build_graph_from_estate(estate)
        graph.validate()  # raises on dangling edges
        assert graph.dangling_edges() == []


def test_ref_markers_stripped_from_node_attributes() -> None:
    estate = render_estate(IntentSampler(2).sample(Archetype.PAYMENTS_API), 2)
    graph = build_graph_from_estate(estate)
    for node in graph.nodes:
        assert not any(k.startswith("__ref__") for k in node.attributes)


def test_subnet_depends_on_vpc() -> None:
    estate = render_estate(IntentSampler(2).sample(Archetype.PAYMENTS_API), 2)
    graph = build_graph_from_estate(estate)
    subnet = next(n.address for n in graph.nodes if n.type == "aws_subnet")
    assert "aws_vpc.main" in graph.neighbours(subnet)


def test_duplicate_node_rejected() -> None:
    graph = EstateGraph()
    graph.add_node(Node("aws_vpc.main", "aws_vpc", "main"))
    with pytest.raises(ValueError, match="duplicate node"):
        graph.add_node(Node("aws_vpc.main", "aws_vpc", "main"))


def test_validate_flags_dangling_edge() -> None:
    graph = EstateGraph()
    graph.add_node(Node("aws_vpc.main", "aws_vpc", "main"))
    graph.add_edge(Edge("aws_vpc.main", "aws_subnet.ghost", DEPENDS_ON))
    with pytest.raises(ValueError, match="dangling"):
        graph.validate()
