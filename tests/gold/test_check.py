"""The gold acceptance check: a compliant configuration is silent, a flawed one is not."""

from __future__ import annotations

import copy

import pytest

from kgcr.corpus.generator import render_estate
from kgcr.corpus.sampler import IntentSampler
from kgcr.gold.check import check_config


def _compliant() -> dict:  # type: ignore[type-arg]
    # A fixture, not gold data: the clean synthetic corpus is silent on the rule floor.
    return render_estate(IntentSampler(3).sample(), 3).to_terraform_json()


def test_a_compliant_configuration_raises_nothing() -> None:
    result = check_config(_compliant())
    assert result.resources > 0 and result.findings == () and result.criticals == ()
    assert result.to_dict()["scope"] == "single-resource rules only"


def test_an_unencrypted_database_is_a_critical() -> None:
    doc = copy.deepcopy(_compliant())
    dbs = doc["resource"].get("aws_db_instance")
    if not dbs:
        doc["resource"]["aws_db_instance"] = {"db": {"engine": "postgres"}}
        dbs = doc["resource"]["aws_db_instance"]
    next(iter(dbs.values()))["storage_encrypted"] = False
    result = check_config(doc)
    assert len(result.criticals) == 1
    assert result.criticals[0]["severity"] == "CRITICAL" and result.criticals[0]["rule"]


@pytest.mark.parametrize(
    "doc", [{}, {"resource": {}}, {"resource": ["x"]}, {"resource": {"aws_vpc": {"a": 1}}}]
)
def test_a_document_that_is_not_a_configuration_is_refused(doc: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(ValueError):
        check_config(doc)
