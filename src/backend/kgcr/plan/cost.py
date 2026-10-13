"""A monthly list-price estimate for a spec, from verified AWS prices (FD-01 S9 cost delta).

This is an estimate of the *priced, steady-state* part of a spec: on-demand list prices,
730 hours a month, Linux, shared tenancy, single-AZ PostgreSQL, gp2 storage. It is not a
bill. Anything the data does not cover is listed, never given a zero or a guess:

* ``not_priced``: resources whose price was not researched, or whose attributes fall outside
  the researched SKUs (a MySQL database, a multi-AZ one);
* ``excluded``: usage-dependent charges no spec can fix (load balancer capacity units, S3
  volume, data transfer, requests, CloudTrail beyond the free first copy).

Prices live in ``aws_prices.json`` with their source and rate codes.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from kgcr.corpus.resources import Resource

__all__ = ["CostEstimate", "CostLine", "UnknownRegion", "estimate", "price_data"]

PRICES_PATH = Path(__file__).with_name("aws_prices.json")


class UnknownRegion(ValueError):
    """No researched prices for this region."""


@dataclass(frozen=True, slots=True)
class CostLine:
    address: str
    item: str
    monthly_usd: float
    basis: str


@dataclass(frozen=True, slots=True)
class CostEstimate:
    region: str
    lines: tuple[CostLine, ...]
    not_priced: tuple[str, ...]
    excluded: tuple[str, ...]
    retrieved_at: str

    @property
    def total_usd(self) -> float:
        return round(sum(line.monthly_usd for line in self.lines), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "total_usd": self.total_usd,
            "retrieved_at": self.retrieved_at,
            "lines": [
                {
                    "address": ln.address,
                    "item": ln.item,
                    "monthly_usd": ln.monthly_usd,
                    "basis": ln.basis,
                }
                for ln in self.lines
            ],
            "not_priced": list(self.not_priced),
            "excluded": list(self.excluded),
        }


@cache
def price_data() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    return data


@cache
def _index() -> dict[tuple[str, str], float]:
    return {(i["key"], i["region"]): float(i["value"]) for i in price_data()["items"]}


def _regions() -> frozenset[str]:
    return frozenset(region for _, region in _index())


def estimate(resources: Sequence[Resource], region: str) -> CostEstimate:
    """The priced monthly cost of ``resources`` in ``region``; raises :class:`UnknownRegion`."""
    if region not in _regions():
        raise UnknownRegion(f"no researched prices for {region!r}; have {sorted(_regions())}")
    hours = float(price_data()["basis"]["hours_per_month"])
    prices = _index()
    lines: list[CostLine] = []
    not_priced: list[str] = []
    excluded: list[str] = []

    def hourly(key: str) -> float | None:
        return prices.get((key, region))

    for res in sorted(resources, key=lambda r: r.address):
        attrs, t = res.attributes, res.type
        if t == "aws_instance":
            kind = str(attrs.get("instance_type"))
            rate = hourly(f"ec2.hourly.{kind}")
            if rate is None:
                not_priced.append(f"{res.address}: no price for instance type {kind}")
            else:
                lines.append(
                    CostLine(
                        res.address,
                        f"{kind} on demand",
                        round(rate * hours, 2),
                        f"{rate} USD/h x {hours:g} h",
                    )
                )
        elif t == "aws_db_instance":
            kind, engine = str(attrs.get("instance_class")), str(attrs.get("engine"))
            rate = hourly(f"rds.postgres.single_az.hourly.{kind}")
            gp2 = hourly("rds.gp2.gb_month")
            if (
                engine != "postgres"
                or str(attrs.get("multi_az")).lower() == "true"
                or rate is None
                or gp2 is None
            ):
                not_priced.append(
                    f"{res.address}: only single-AZ PostgreSQL on a researched class is priced "
                    f"(engine {engine}, class {kind}, multi_az {attrs.get('multi_az', False)})"
                )
                continue
            storage = float(attrs.get("allocated_storage", 0))
            lines.append(
                CostLine(
                    res.address,
                    f"{kind} instance",
                    round(rate * hours, 2),
                    f"{rate} USD/h x {hours:g} h",
                )
            )
            lines.append(
                CostLine(
                    res.address,
                    f"{storage:g} GB gp2 storage",
                    round(storage * gp2, 2),
                    f"{storage:g} GB x {gp2} USD/GB-month",
                )
            )
        elif t == "aws_lb":
            rate = hourly("alb.hourly")
            if attrs.get("load_balancer_type", "application") != "application" or rate is None:
                not_priced.append(f"{res.address}: only application load balancers are priced")
            else:
                lines.append(
                    CostLine(
                        res.address,
                        "application load balancer",
                        round(rate * hours, 2),
                        f"{rate} USD/h x {hours:g} h",
                    )
                )
                excluded.append(f"{res.address}: load balancer capacity units are usage-dependent")
        elif t == "aws_kms_key":
            rate = hourly("kms.key_month")
            if rate is None:
                not_priced.append(f"{res.address}: no KMS price")
            else:
                lines.append(
                    CostLine(
                        res.address, "customer managed key", rate, f"{rate} USD per key per month"
                    )
                )
                excluded.append(f"{res.address}: request charges are usage-dependent")
        elif t == "aws_cloudtrail":
            lines.append(
                CostLine(
                    res.address,
                    "first copy of management events",
                    0.0,
                    "official rate 0.0 per event",
                )
            )
            excluded.append(f"{res.address}: additional copies and data events are usage-dependent")
        elif t == "aws_s3_bucket":
            excluded.append(
                f"{res.address}: storage volume is unknown "
                f"(USD {hourly('s3.standard.gb_month')} per GB-month, first 50 TB)"
            )
        elif t == "aws_glue_catalog_database":
            excluded.append(
                f"{res.address}: catalog object count is unknown (free up to 1,000,000 objects)"
            )
        else:
            not_priced.append(f"{res.address}: no price researched for {t}")
    return CostEstimate(
        region=region,
        lines=tuple(lines),
        not_priced=tuple(not_priced),
        excluded=tuple(excluded),
        retrieved_at=str(price_data()["retrieved_at"]),
    )
