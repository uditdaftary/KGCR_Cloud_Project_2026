"""The second labeller's parser, kappa, and the three-engine comparison (fake engines)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kgcr.corpus.estate import Estate
from kgcr.corpus.pipeline import generate_corpus
from kgcr.defects.inject import applicable_injectors
from kgcr.labelling import trivy_engine
from kgcr.labelling.agreement import agreement, cohen_kappa, evaluate_labellers
from kgcr.labelling.checkov_engine import CheckovFinding
from kgcr.labelling.trivy_engine import TrivyFinding, parse_trivy_json, run_trivy

FIXTURE = Path(__file__).parent / "fixtures" / "trivy_sample.json"


def test_the_parser_keeps_failures_with_a_resource_and_drops_the_rest() -> None:
    # The fixture is real `trivy config` output (Trivy 0.75.0) over an estate with an
    # unencrypted database, trimmed, plus one entry with no resource and one PASS.
    findings = parse_trivy_json(json.loads(FIXTURE.read_text(encoding="utf-8")))
    ids = {(f.check_id, f.resource) for f in findings}
    assert ("AWS-0080", "aws_db_instance.cardholder") in ids  # RDS encryption not enabled
    assert all(f.check_id not in {"AWS-9999", "AWS-9998"} for f in findings)
    assert all(isinstance(f, TrivyFinding) and f.resource for f in findings)


@pytest.mark.parametrize("data", [None, [], "x", {"Results": None}, {"Results": [{}]}])
def test_a_surprising_document_is_no_findings_not_a_crash(data: object) -> None:
    assert parse_trivy_json(data) == []


def test_a_missing_binary_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trivy_engine, "trivy_binary", lambda: None)
    estate = generate_corpus(1, 1)[0]
    with pytest.raises(RuntimeError, match="not installed"):
        run_trivy(estate)


@pytest.mark.skipif(not trivy_engine.trivy_available(), reason="trivy is not installed")
def test_the_real_binary_flags_the_unencrypted_database() -> None:
    corpus = generate_corpus(40, 1729)
    est = next(
        e
        for e in corpus
        if any(i.variant == "unencrypted_database" for i in applicable_injectors(e))
    )
    defected = next(
        i for i in applicable_injectors(est) if i.variant == "unencrypted_database"
    ).run(est)
    site = defected.defect.injection_site[0]
    assert ("AWS-0080", site) in {(f.check_id, f.resource) for f in run_trivy(defected.estate)}
    assert "AWS-0080" not in {f.check_id for f in run_trivy(est) if f.resource == site}


def test_kappa_known_values() -> None:
    assert cohen_kappa([True, True, False, False], [True, True, False, False]) == 1.0
    assert cohen_kappa([True, True, False, False], [True, False, False, False]) == 0.5
    assert cohen_kappa([True, False, True, False], [False, True, False, True]) == -1.0
    assert cohen_kappa([True, True], [True, True]) is None  # no variance: kappa is undefined
    with pytest.raises(ValueError):
        cohen_kappa([True], [True, False])


def test_percent_agreement() -> None:
    assert (
        agreement([True, False, True, False], [True, False, False, False])["percent_agreement"]
        == 0.75
    )


def _pairs(n: int = 4) -> dict[str, list[tuple[Estate, Estate, str]]]:
    out: list[tuple[Estate, Estate, str]] = []
    for est in generate_corpus(80, 1729):
        injectors = [i for i in applicable_injectors(est) if i.variant == "unencrypted_database"]
        if injectors:
            defected = injectors[0].run(est)
            out.append((est, defected.estate, defected.defect.injection_site[0]))
        if len(out) == n:
            break
    return {"unencrypted_database": out}


def _flagged_unencrypted(estate: Estate, site: str) -> bool:
    return any(
        r.address == site and r.attributes.get("storage_encrypted") is False
        for r in estate.resources
    )


def test_three_engines_are_compared_on_seeded_and_clean_units() -> None:
    pairs = _pairs()
    sites = {id(p[1]): p[2] for p in pairs["unencrypted_database"]}

    def checkov(estate: Estate) -> list[CheckovFinding]:  # perfect on this family
        return [
            CheckovFinding("CKV_AWS_16", r.address, False)
            for r in estate.resources
            if r.attributes.get("storage_encrypted") is False
        ]

    def trivy(estate: Estate) -> list[TrivyFinding]:  # flags the database every time
        return [
            TrivyFinding("AWS-0080", r.address, "")
            for r in estate.resources
            if r.type == "aws_db_instance"
        ]

    report = evaluate_labellers(pairs, checkov, trivy)
    fam = next(f for f in report["families"] if f["family"] == "unencrypted_database")
    n = len(pairs["unencrypted_database"])
    assert fam["seeded_defects"] == n and fam["clean_resources"] == n
    assert fam["seeded_recall"] == {"rule_floor": 1.0, "checkov": 1.0, "trivy": 1.0}
    assert fam["false_positives_on_clean"] == {"rule_floor": 0, "checkov": 0, "trivy": n}
    assert fam["pairwise"]["rule_floor_vs_checkov"]["kappa"] == 1.0
    assert (
        fam["pairwise"]["rule_floor_vs_trivy"]["kappa"] == 0.0
    )  # trivy always flags: chance level
    # a family with no samples reports no recall rather than a made-up number
    empty = next(f for f in report["families"] if f["family"] == "open_security_group")
    assert empty["seeded_defects"] == 0 and empty["seeded_recall"]["trivy"] is None
    assert sites  # the injected site was real
