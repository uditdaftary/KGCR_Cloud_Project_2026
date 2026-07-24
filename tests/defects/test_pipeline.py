"""The pipeline injects in quantity, covers all classes, and passes the DF-7 gate."""

from __future__ import annotations

import json

from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import (
    Archetype,
    AZSpread,
    IAMShape,
    Intent,
    LoggingPosture,
    NetworkLayout,
    Scale,
    TaggingDiscipline,
)
from kgcr.corpus.pipeline import generate_corpus
from kgcr.defects.pipeline import (
    df7_set,
    inject_corpus,
    summarise_defects,
    verify_df7_gate,
    write_defect_corpus,
)
from kgcr.defects.taxonomy import DefectClass


def _clean_corpus():
    """A small, deterministic clean corpus covering all three archetypes and the
    shapes every injector needs."""
    payments = Intent(
        archetype=Archetype.PAYMENTS_API,
        region="eu-west-2",
        az_spread=AZSpread.TWO_AZ,
        network_layout=NetworkLayout.PUBLIC_PRIVATE,
        logging=LoggingPosture.FULL,
        iam_shape=IAMShape.LEAST_PRIVILEGE,
        tagging=TaggingDiscipline.STRICT,
        scale=Scale.MEDIUM,
    )
    customer = Intent(
        archetype=Archetype.CUSTOMER_DATA_PLATFORM,
        region="eu-west-1",
        az_spread=AZSpread.TWO_AZ,
        network_layout=NetworkLayout.PUBLIC_PRIVATE,
        logging=LoggingPosture.FULL,
        iam_shape=IAMShape.ROLE_PER_SERVICE,
        tagging=TaggingDiscipline.PARTIAL,
        scale=Scale.SMALL,
    )
    reporting = Intent(
        archetype=Archetype.INTERNAL_REPORTING,
        region="us-east-1",
        az_spread=AZSpread.SINGLE_AZ,
        network_layout=NetworkLayout.PUBLIC_ONLY,
        logging=LoggingPosture.MINIMAL,
        iam_shape=IAMShape.LEAST_PRIVILEGE,
        tagging=TaggingDiscipline.POOR,
        scale=Scale.LARGE,
    )
    return [render_estate(i, s) for i, s in ((payments, 1), (customer, 2), (reporting, 3))]


def test_inject_corpus_covers_all_seven_classes() -> None:
    defected = inject_corpus(_clean_corpus())
    summary = summarise_defects(defected)
    assert set(summary["classes_present"]) == {c.value for c in DefectClass}


def test_df7_is_produced_in_quantity() -> None:
    # Every estate contributes its relational variants, so DF-7 is a set, not a
    # handful of exemplars (FD-05 §5: "deliberately and in quantity").
    defected = inject_corpus(_clean_corpus())
    df7 = df7_set(defected)
    assert len(df7) >= 6  # 3 estates x at least 2 relational variants each
    assert all(d.defect.defect_class is DefectClass.RELATIONAL for d in df7)


def test_df7_gate_passes_on_the_generated_corpus() -> None:
    defected = inject_corpus(_clean_corpus())
    report = verify_df7_gate(defected)
    assert report.df7_estates > 0
    assert report.single_resource_clean, report.single_resource_offenders
    assert report.paths_recovered, report.unrecovered_paths
    assert report.passed


def test_gate_holds_over_a_randomly_sampled_corpus() -> None:
    # Same invariant over the real generator path, not just hand-built intents.
    # DF-7 is gated on a sensitive sink, so the count depends on how many sampled
    # estates are payments/customer-data; the gate must hold whatever that count.
    defected = inject_corpus(generate_corpus(20, seed=1729))
    report = verify_df7_gate(defected)
    assert report.df7_estates > 0
    assert report.passed


def test_injected_defects_keep_parent_seed_families() -> None:
    clean = _clean_corpus()
    families = {e.seed_family for e in clean}
    for item in inject_corpus(clean):
        assert item.defect.seed_family in families


def test_write_defect_corpus_emits_artifacts_and_manifest(tmp_path) -> None:
    defected = inject_corpus(_clean_corpus())
    manifest = write_defect_corpus(defected, tmp_path)

    assert manifest["df7_gate"]["passed"] is True
    assert len(manifest["defects"]) == len(defected)
    assert manifest["relational_split"] == [d.estate.estate_id for d in df7_set(defected)]

    # Every defect estate wrote its three artifacts.
    for item in defected:
        base = tmp_path / "estates" / item.estate.estate_id
        assert base.with_suffix(".tf.json").exists()
        assert base.with_suffix(".graph.json").exists()
        defect_doc = json.loads(base.with_suffix(".defect.json").read_text(encoding="utf-8"))
        assert defect_doc["defect_class"] == item.defect.defect_class.value

    written = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert written["summary"]["df7_defects"] == len(df7_set(defected))
