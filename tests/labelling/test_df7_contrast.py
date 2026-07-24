"""The DF-7 contrast: graph recovers the path, the engine is blind to the sink.

The contrast logic is tested with stub labellers (fast, deterministic). A guarded
live test runs the real Checkov contrast where Checkov is installed.
"""

from __future__ import annotations

import pytest

from kgcr.corpus.estate import Estate
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
from kgcr.labelling.checkov_engine import CheckovFinding, checkov_available
from kgcr.labelling.df7_contrast import evaluate_df7_visibility

_SINK = "aws_db_instance.cardholder"


def _payments(seed: int) -> Estate:
    intent = Intent(
        archetype=Archetype.PAYMENTS_API,
        region="eu-west-2",
        az_spread=AZSpread.TWO_AZ,
        network_layout=NetworkLayout.PUBLIC_PRIVATE,
        logging=LoggingPosture.FULL,
        iam_shape=IAMShape.LEAST_PRIVILEGE,
        tagging=TaggingDiscipline.STRICT,
        scale=Scale.MEDIUM,
    )
    return render_estate(intent, seed)


def _blind_labeller(estate: Estate) -> list[CheckovFinding]:
    # A verdict that is a pure function of each resource, so the pre-existing
    # sink scores identically in parent and defect estates.
    return [
        CheckovFinding("CKV_STUB", r.address, r.type == "aws_kms_key") for r in estate.resources
    ]


def _reactive_labeller(estate: Estate) -> list[CheckovFinding]:
    # A hypothetical engine that DOES react to the injected wiring by flagging
    # the sink — the case the contrast must be able to detect as "not blind".
    findings = _blind_labeller(estate)
    if any(r.name.startswith("df7_") for r in estate.resources):
        findings.append(CheckovFinding("CKV2_REACHABILITY", _SINK, False))
    return findings


def test_engine_blind_labeller_makes_c1_hold() -> None:
    corpus = [_payments(1), _payments(2)]
    report = evaluate_df7_visibility(corpus, labeller=_blind_labeller)
    assert report.total == 6  # 2 estates x 3 relational variants
    assert report.graph_recovered == 6
    assert report.engine_blind == 6
    assert report.c1_holds_for_all


def test_reactive_engine_is_detected_as_not_blind() -> None:
    corpus = [_payments(1), _payments(2)]
    report = evaluate_df7_visibility(corpus, labeller=_reactive_labeller)
    assert report.graph_recovered == 6  # the graph still recovers every path
    assert report.engine_blind == 0  # the sink verdict changed on every one
    assert not report.c1_holds_for_all
    # The transparency fields record what changed.
    assert all("CKV2_REACHABILITY" in c.sink_checks_added for c in report.contrasts)


def test_no_df7_estates_yields_empty_report() -> None:
    # An internal-reporting estate has no sensitive sink, so no DF-7 applies.
    reporting = render_estate(
        Intent(
            archetype=Archetype.INTERNAL_REPORTING,
            region="us-east-1",
            az_spread=AZSpread.SINGLE_AZ,
            network_layout=NetworkLayout.PUBLIC_ONLY,
            logging=LoggingPosture.MINIMAL,
            iam_shape=IAMShape.LEAST_PRIVILEGE,
            tagging=TaggingDiscipline.POOR,
            scale=Scale.SMALL,
        ),
        3,
    )
    report = evaluate_df7_visibility([reporting], labeller=_blind_labeller)
    assert report.total == 0
    assert not report.c1_holds_for_all  # vacuously false: nothing to hold


@pytest.mark.skipif(not checkov_available(), reason="checkov not installed")
def test_live_checkov_is_blind_to_df7() -> None:
    report = evaluate_df7_visibility([_payments(7)])
    assert report.total == 3
    assert report.c1_holds_for_all, [c.to_dict() for c in report.contrasts]
