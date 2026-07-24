"""The Checkov output parser is exercised against a committed fixture.

The parser is tested without a live Checkov run (slow, version-fragile); the
fixture is real Checkov JSON captured once. A single live smoke test runs only
where Checkov is installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.corpus.intent import Archetype
from kgcr.corpus.sampler import IntentSampler
from kgcr.labelling.checkov_engine import (
    CheckovFinding,
    checkov_available,
    parse_checkov_json,
    resource_verdict,
    run_checkov,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "checkov_sample.json"


def test_parses_passed_and_failed_from_fixture() -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    findings = parse_checkov_json(data)
    assert findings, "fixture should yield findings"
    assert any(f.passed for f in findings)
    assert any(not f.passed for f in findings)
    # Every finding is well-formed.
    for f in findings:
        assert f.check_id.startswith("CKV")
        assert f.resource


def test_parse_accepts_both_list_and_dict_shapes() -> None:
    run = {"results": {"passed_checks": [{"check_id": "CKV_AWS_1", "resource": "r"}]}}
    from_dict = parse_checkov_json(run)
    from_list = parse_checkov_json([run])
    assert from_dict == from_list
    assert from_dict == [CheckovFinding("CKV_AWS_1", "r", True)]


def test_resource_verdict_is_order_independent() -> None:
    findings = [
        CheckovFinding("CKV_AWS_2", "db", False),
        CheckovFinding("CKV_AWS_1", "db", True),
        CheckovFinding("CKV_AWS_9", "other", True),
    ]
    verdict = resource_verdict(findings, "db")
    assert verdict == frozenset({("CKV_AWS_1", True), ("CKV_AWS_2", False)})
    # A different insertion order yields the same set.
    assert resource_verdict(list(reversed(findings)), "db") == verdict


@pytest.mark.skipif(not checkov_available(), reason="checkov not installed")
def test_live_checkov_scores_the_estate() -> None:
    estate = render_estate(IntentSampler(1).sample(Archetype.PAYMENTS_API), 1)
    findings = run_checkov(estate)
    assert findings, "checkov should return findings for a real estate"
    assert any(f.resource == "aws_db_instance.cardholder" for f in findings)
