"""The terraform-plan-JSON parser builds the same graph shape as the IR path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kgcr.corpus.plan_parser import parse_plan_json

FIXTURE = Path(__file__).parent / "fixtures" / "plan_sample.json"


@pytest.fixture
def plan() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_managed_resources_become_nodes_including_child_modules(plan: dict) -> None:
    graph = parse_plan_json(plan, estate_id="fixture")
    addresses = {n.address for n in graph.nodes}
    assert addresses == {
        "aws_vpc.main",
        "aws_subnet.private_0",
        "aws_security_group.app",
        "module.logging.aws_s3_bucket.logs",
    }


def test_data_sources_are_not_nodes(plan: dict) -> None:
    graph = parse_plan_json(plan)
    assert not any(n.address.startswith("data.") for n in graph.nodes)


def test_node_attributes_come_from_planned_values(plan: dict) -> None:
    graph = parse_plan_json(plan)
    assert graph.node("aws_vpc.main").attributes["cidr_block"] == "10.20.0.0/16"


def test_reference_expressions_become_dependency_edges(plan: dict) -> None:
    graph = parse_plan_json(plan)
    assert "aws_vpc.main" in graph.neighbours("aws_subnet.private_0")
    assert "aws_vpc.main" in graph.neighbours("aws_security_group.app")


def test_references_to_data_sources_are_dropped(plan: dict) -> None:
    # The security group references data.aws_caller_identity, which is not a
    # managed resource, so it must not produce an edge.
    graph = parse_plan_json(plan)
    targets = graph.neighbours("aws_security_group.app")
    assert all(not t.startswith("data.") for t in targets)


def test_edges_are_deduplicated(plan: dict) -> None:
    graph = parse_plan_json(plan)
    pairs = [(e.source, e.target) for e in graph.edges]
    assert len(pairs) == len(set(pairs))


def test_no_dangling_edges(plan: dict) -> None:
    parse_plan_json(plan).validate()


def test_empty_plan_yields_empty_graph() -> None:
    graph = parse_plan_json({})
    assert graph.node_count == 0
    assert graph.edge_count == 0
