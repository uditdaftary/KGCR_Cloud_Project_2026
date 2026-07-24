"""The taxonomy is complete, and the ground-truth record round-trips."""

from __future__ import annotations

from kgcr.defects.taxonomy import (
    DEFAULT_CONTROL,
    DEFAULT_SEVERITY,
    DETECTABILITY,
    DefectClass,
    DefectInstance,
    Detectability,
    Severity,
)


def test_all_seven_classes_have_a_control_and_severity() -> None:
    for cls in DefectClass:
        assert cls in DEFAULT_CONTROL
        assert DEFAULT_CONTROL[cls].startswith("kg://control/")
        assert isinstance(DEFAULT_SEVERITY[cls], Severity)


def test_relational_is_the_only_single_resource_undetectable_class() -> None:
    assert DETECTABILITY[DefectClass.RELATIONAL] is Detectability.NONE
    detectable = [c for c in DefectClass if DETECTABILITY[c] is not Detectability.NONE]
    assert DefectClass.RELATIONAL not in detectable
    assert len(detectable) == 6


def test_relational_defects_are_critical() -> None:
    # Severity attaches to the control, and relational reachability breaches a
    # mandatory PCI clause (FD-07 §6).
    assert DEFAULT_SEVERITY[DefectClass.RELATIONAL] is Severity.CRITICAL


def test_defect_instance_hop_count_and_serialisation() -> None:
    defect = DefectInstance(
        defect_class=DefectClass.RELATIONAL,
        variant="indirect_internet_reachability",
        estate_id="abc",
        parent_estate_id="parent",
        seed_family="fam-1-0",
        control="kg://control/pci-dss-v4/1.3",
        severity=Severity.CRITICAL,
        injection_site=("aws_instance.hop",),
        expected_finding="reachable",
        evidence_path=("a", "b", "c", "d"),
    )
    assert defect.hop_count == 3
    assert defect.is_relational
    d = defect.to_dict()
    assert d["hop_count"] == 3
    assert d["detectability"] == "no"
    assert d["evidence_path"] == ["a", "b", "c", "d"]


def test_single_resource_defect_has_zero_hops() -> None:
    defect = DefectInstance(
        defect_class=DefectClass.EXPOSURE,
        variant="open_security_group",
        estate_id="abc",
        parent_estate_id="parent",
        seed_family="fam-1-0",
        control=DEFAULT_CONTROL[DefectClass.EXPOSURE],
        severity=DEFAULT_SEVERITY[DefectClass.EXPOSURE],
        injection_site=("aws_security_group.app",),
        expected_finding="open",
    )
    assert defect.hop_count == 0
    assert not defect.is_relational
