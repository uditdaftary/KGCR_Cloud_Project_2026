"""The estimator prices only what the verified data covers and says what it left out."""

from __future__ import annotations

import json

import pytest

from kgcr.corpus.resources import Resource
from kgcr.plan.cost import PRICES_PATH, UnknownRegion, estimate, price_data


def _db(**attrs: object) -> Resource:
    base = {"engine": "postgres", "instance_class": "db.t3.small", "allocated_storage": 20}
    return Resource("aws_db_instance", "cardholder", {**base, **attrs})


def test_an_instance_is_the_hourly_rate_times_730_hours() -> None:
    got = estimate([Resource("aws_instance", "app", {"instance_type": "t3.small"})], "eu-west-1")
    assert [(ln.item, ln.monthly_usd) for ln in got.lines] == [("t3.small on demand", 16.64)]
    assert got.total_usd == 16.64 and got.not_priced == ()


def test_a_database_adds_its_storage_at_the_gp2_rate() -> None:
    got = estimate([_db()], "eu-west-1")
    assert [ln.monthly_usd for ln in got.lines] == [28.47, 2.54]
    assert got.total_usd == 31.01


@pytest.mark.parametrize(
    "attrs", [{"engine": "mysql"}, {"multi_az": True}, {"instance_class": "db.r9.huge"}]
)
def test_a_database_outside_the_researched_skus_is_not_priced_not_zeroed(
    attrs: dict[str, object],
) -> None:
    got = estimate([_db(**attrs)], "eu-west-1")
    assert got.lines == () and got.total_usd == 0.0
    assert got.not_priced and "aws_db_instance.cardholder" in got.not_priced[0]


def test_usage_dependent_and_unresearched_items_are_listed_not_priced() -> None:
    got = estimate(
        [
            Resource("aws_lb", "api", {"load_balancer_type": "application"}),
            Resource("aws_s3_bucket", "logs", {}),
            Resource("aws_vpc", "main", {}),
        ],
        "us-east-1",
    )
    assert got.total_usd == 16.43  # 0.0225 USD/h x 730 h, the load balancer only
    assert any("capacity units" in e for e in got.excluded)
    assert any("aws_s3_bucket.logs" in e and "volume is unknown" in e for e in got.excluded)
    assert got.not_priced == ("aws_vpc.main: no price researched for aws_vpc",)


def test_an_unknown_region_raises() -> None:
    with pytest.raises(UnknownRegion):
        estimate([], "ap-south-1")


def test_the_total_is_the_sum_of_the_lines() -> None:
    got = estimate(
        [_db(), Resource("aws_kms_key", "main", {}), Resource("aws_lb", "api", {})], "eu-west-2"
    )
    assert got.total_usd == round(sum(ln.monthly_usd for ln in got.lines), 2)
    assert json.loads(json.dumps(got.to_dict()))["total_usd"] == got.total_usd


def test_every_price_carries_its_source_and_rate_code() -> None:
    data = price_data()
    assert (
        data["basis"]["hours_per_month"] == 730 and "own convention" in data["basis"]["hours_note"]
    )
    assert PRICES_PATH.name == "aws_prices.json"
    for item in data["items"]:
        assert item["source_url"].startswith("https://pricing.us-east-1.amazonaws.com/offers/")
        assert item["rate_code"] and item["value"] is not None
