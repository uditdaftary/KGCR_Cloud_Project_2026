"""The corpus pipeline satisfies the Phase 3 gate: N estates, into the graph."""

from __future__ import annotations

import json

import pytest

from kgcr.corpus.pipeline import generate_corpus, summarise_corpus, write_corpus


def test_generates_requested_count() -> None:
    assert len(generate_corpus(50, seed=1)) == 50


def test_is_reproducible_for_a_seed() -> None:
    a = [e.to_dict() for e in generate_corpus(30, seed=1)]
    b = [e.to_dict() for e in generate_corpus(30, seed=1)]
    assert a == b


def test_every_estate_carries_ground_truth_intent() -> None:
    for estate in generate_corpus(60, seed=2):
        assert estate.intent is not None
        assert estate.intent.intent_hash


def test_gate_500_estates_all_unique_and_into_the_graph() -> None:
    # The Phase 3 exit gate: 500 estates generated and parsed into the graph.
    estates = generate_corpus(500, seed=1729)
    summary = summarise_corpus(estates)
    assert summary["estates"] == 500
    assert summary["unique_estate_ids"] == 500
    assert summary["total_graph_nodes"] > 500  # many resources per estate
    # summarise_corpus validates each graph; reaching here means none dangled.
    assert set(summary["archetypes"]) == {
        "payments_api",
        "customer_data_platform",
        "internal_reporting",
    }


def test_family_size_groups_estates() -> None:
    estates = generate_corpus(40, seed=3, family_size=4)
    summary = summarise_corpus(estates)
    assert summary["estates"] == 40
    assert summary["seed_families"] == 10


def test_write_corpus_emits_artifacts_and_manifest(tmp_path) -> None:  # type: ignore[no-untyped-def]
    estates = generate_corpus(12, seed=4)
    manifest = write_corpus(estates, tmp_path)
    assert manifest["summary"]["estates"] == 12

    assert (tmp_path / "manifest.json").exists()
    loaded = json.loads((tmp_path / "manifest.json").read_text())
    assert loaded["summary"]["estates"] == 12
    assert len(loaded["estates"]) == 12

    # Each estate has its three artifacts, including the ground-truth intent.
    for estate in estates:
        base = tmp_path / "estates" / estate.estate_id
        assert base.with_suffix(".tf.json").exists()
        assert base.with_suffix(".graph.json").exists()
        intent_file = base.with_suffix(".intent.json")
        assert intent_file.exists()
        assert json.loads(intent_file.read_text())["archetype"] == estate.intent.archetype.value


def test_negative_count_rejected() -> None:
    with pytest.raises(ValueError):
        generate_corpus(-1)


def test_zero_family_size_rejected() -> None:
    with pytest.raises(ValueError):
        generate_corpus(5, family_size=0)
