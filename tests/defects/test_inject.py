"""Injection is deterministic, keeps lineage, and gives DF-7 its defining property."""

from __future__ import annotations

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.corpus.graph import build_graph_from_estate
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
from kgcr.defects.detectors import relational_path_exists, single_resource_findings
from kgcr.defects.inject import applicable_injectors
from kgcr.defects.taxonomy import DETECTABILITY, DefectClass, Detectability

# A fully-loaded payments estate so every injector applies: public layout gives
# the internet gateway and a public subnet, FULL logging gives a CloudTrail.
_FULL_INTENT = Intent(
    archetype=Archetype.PAYMENTS_API,
    region="eu-west-2",
    az_spread=AZSpread.TWO_AZ,
    network_layout=NetworkLayout.PUBLIC_PRIVATE,
    logging=LoggingPosture.FULL,
    iam_shape=IAMShape.LEAST_PRIVILEGE,
    tagging=TaggingDiscipline.STRICT,
    scale=Scale.MEDIUM,
)


def _estate():
    return render_estate(_FULL_INTENT, 7)


def test_every_injector_applies_to_the_fully_loaded_estate() -> None:
    assert len(applicable_injectors(_estate())) == 9


def test_injection_is_deterministic() -> None:
    estate = _estate()
    for injector in applicable_injectors(estate):
        a = injector.run(estate)
        b = injector.run(estate)
        assert a.estate.to_dict() == b.estate.to_dict()
        assert a.defect.to_dict() == b.defect.to_dict()


def test_injected_estate_has_a_distinct_id_and_preserves_lineage() -> None:
    estate = _estate()
    seen: set[str] = set()
    for injector in applicable_injectors(estate):
        result = injector.run(estate)
        assert result.estate.estate_id != estate.estate_id
        assert result.estate.estate_id not in seen, "variants must not collide"
        seen.add(result.estate.estate_id)
        # Lineage for the split (FD-05 §9): parent id recorded, seed family kept.
        assert result.defect.parent_estate_id == estate.estate_id
        assert result.defect.seed_family == estate.seed_family
        assert result.estate.seed_family == estate.seed_family


def test_ground_truth_is_complete() -> None:
    estate = _estate()
    for injector in applicable_injectors(estate):
        defect = injector.run(estate).defect
        assert defect.control.startswith("kg://control/")
        assert defect.injection_site
        assert defect.expected_finding
        assert defect.defect_class is injector.defect_class


def test_single_resource_defects_trip_the_oracle_at_the_injection_site() -> None:
    estate = _estate()
    for injector in applicable_injectors(estate):
        if DETECTABILITY[injector.defect_class] is not Detectability.FULL:
            continue
        result = injector.run(estate)
        findings = single_resource_findings(result.estate)
        assert findings, f"{injector.variant} produced no single-resource finding"
        sites = set(result.defect.injection_site)
        assert any(f.address in sites for f in findings)


def test_df7_defects_are_single_resource_clean() -> None:
    # The defining property: a relational defect adds no individually
    # non-compliant resource, so single-resource engines score zero on it.
    estate = _estate()
    for injector in applicable_injectors(estate):
        if injector.defect_class is not DefectClass.RELATIONAL:
            continue
        result = injector.run(estate)
        assert single_resource_findings(result.estate) == [], injector.variant


def test_df7_paths_are_recoverable_within_the_hop_bound() -> None:
    estate = _estate()
    for injector in applicable_injectors(estate):
        if injector.defect_class is not DefectClass.RELATIONAL:
            continue
        result = injector.run(estate)
        path = result.defect.evidence_path
        assert len(path) >= 2
        assert result.defect.hop_count <= 3
        recovered = relational_path_exists(result.estate, path[0], path[-1], hop_bound=3)
        assert recovered is not None, f"{injector.variant}: graph cannot reach the sink"


def test_injected_estates_build_valid_graphs() -> None:
    estate = _estate()
    for injector in applicable_injectors(estate):
        graph = build_graph_from_estate(injector.run(estate).estate)
        graph.validate()  # raises on dangling edges
        addresses = [n.address for n in graph.nodes]
        assert len(addresses) == len(set(addresses))


def test_injected_resources_use_only_real_terraform_arguments() -> None:
    # An injector must never carry semantics in a fake attribute: to_terraform_json
    # renders every non-__ref__ attribute as a real resource argument, so a
    # synthetic key would emit invalid HCL and break the plan-based labelling
    # engines (P4). Guard against the whole class by rejecting df7_-prefixed
    # argument keys in the rendered config.
    estate = _estate()
    for injector in applicable_injectors(estate):
        tf = injector.run(estate).estate.to_terraform_json()
        for by_name in tf["resource"].values():
            for body in by_name.values():
                assert not any(k.startswith("df7_") for k in body), injector.variant


@pytest.mark.parametrize("archetype", list(Archetype))
def test_single_resource_injectors_apply_to_every_archetype(archetype: Archetype) -> None:
    from kgcr.corpus.sampler import IntentSampler

    estate = render_estate(IntentSampler(1).sample(archetype), 1)
    variants = {inj.variant for inj in applicable_injectors(estate)}
    # These apply regardless of archetype or layout.
    assert {"open_security_group", "wildcard_iam_policy"} <= variants


def test_df7_is_gated_on_a_sensitive_sink() -> None:
    from kgcr.corpus.sampler import IntentSampler

    # Payments and customer-data estates hold a sensitive store, so DF-7 applies;
    # the low-sensitivity reporting archetype (FD-05 §3 contrast case) must not
    # accumulate relational CRITICALs.
    def df7_variants(archetype: Archetype) -> set[str]:
        estate = render_estate(IntentSampler(3).sample(archetype), 3)
        return {
            inj.variant
            for inj in applicable_injectors(estate)
            if inj.defect_class is DefectClass.RELATIONAL
        }

    assert "transitive_trust_chain" in df7_variants(Archetype.PAYMENTS_API)
    assert "transitive_trust_chain" in df7_variants(Archetype.CUSTOMER_DATA_PLATFORM)
    assert df7_variants(Archetype.INTERNAL_REPORTING) == set()
