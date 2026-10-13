"""Do labelling engines agree with each other and with the seeded truth? (FD-05 section 6)

Each engine answers one binary question per (estate, resource) in a family: flagged or not.
Agreement is reported as percent agreement and Cohen's kappa, which discounts the agreement
two engines would reach by chance. Kappa is undefined when chance agreement is already total
(an engine that never varies), and is then reported as None, not as a number.

The family map says which check ids from each engine count as the same defect. It is this
project's own mapping, and where the engines define the defect differently (the injected
world-open port 443 is not a violation to Checkov or Trivy) the disagreement is the finding.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from kgcr.corpus.estate import Estate
from kgcr.defects.detectors import resource_findings
from kgcr.labelling.checkov_engine import CheckovFinding
from kgcr.labelling.trivy_engine import TrivyFinding

__all__ = ["FAMILIES", "AgreementFamily", "agreement", "cohen_kappa", "evaluate_labellers"]


@dataclass(frozen=True, slots=True)
class AgreementFamily:
    key: str
    label: str
    resource_type: str
    rule_floor: frozenset[str]
    checkov: frozenset[str]
    trivy: frozenset[str]


FAMILIES: tuple[AgreementFamily, ...] = (
    AgreementFamily(
        "open_security_group",
        "DF-1 security group open to the world",
        "aws_security_group",
        frozenset({"CKV_AWS_260"}),
        frozenset({"CKV_AWS_260", "CKV_AWS_24", "CKV_AWS_25", "CKV_AWS_277"}),
        frozenset({"AWS-0107"}),
    ),
    AgreementFamily(
        "unencrypted_database",
        "DF-2 database storage not encrypted",
        "aws_db_instance",
        frozenset({"CKV_AWS_16"}),
        frozenset({"CKV_AWS_16"}),
        frozenset({"AWS-0080"}),
    ),
    AgreementFamily(
        "wildcard_iam_policy",
        "DF-3 IAM policy allows Action * on Resource *",
        "aws_iam_role_policy",
        frozenset({"CKV_AWS_1"}),
        frozenset({"CKV_AWS_1", "CKV_AWS_49", "CKV_AWS_63"}),
        frozenset({"AWS-0057"}),
    ),
    AgreementFamily(
        "cloudtrail_no_log_validation",
        "DF-4 CloudTrail log-file validation off",
        "aws_cloudtrail",
        frozenset({"CKV_AWS_36"}),
        frozenset({"CKV_AWS_36"}),
        frozenset({"AWS-0016"}),
    ),
)


def cohen_kappa(a: Sequence[bool], b: Sequence[bool]) -> float | None:
    """Cohen's kappa for two binary raters; None when chance agreement is already total."""
    if len(a) != len(b) or not a:
        raise ValueError("two non-empty ratings of the same length are needed")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    chance = pa * pb + (1 - pa) * (1 - pb)
    if chance == 1.0:
        return None
    return round((observed - chance) / (1 - chance), 3)


def agreement(a: Sequence[bool], b: Sequence[bool]) -> dict[str, Any]:
    n = len(a)
    return {
        "n": n,
        "percent_agreement": round(sum(x == y for x, y in zip(a, b, strict=True)) / n, 3)
        if n
        else None,
        "kappa": cohen_kappa(a, b) if n else None,
    }


def evaluate_labellers(
    pairs: dict[str, Sequence[tuple[Estate, Estate, str]]],
    run_checkov: Callable[[Estate], Sequence[CheckovFinding]],
    run_trivy: Callable[[Estate], Sequence[TrivyFinding]],
) -> dict[str, Any]:
    """Seeded recall, false positives and pairwise agreement for the three engines.

    ``pairs[family_key]`` holds ``(clean, defected, injection_site_address)`` triples. Each
    triple contributes two units: the site resource in the clean estate (truth: not defective)
    and in the defected one (truth: defective).
    """
    out: list[dict[str, Any]] = []
    for family in FAMILIES:
        units: list[tuple[bool, bool, bool, bool]] = []  # truth, rule floor, checkov, trivy
        for clean, defected, site in pairs.get(family.key, ()):
            for estate, truth in ((clean, False), (defected, True)):
                ckv = {
                    f.check_id for f in run_checkov(estate) if not f.passed and f.resource == site
                }
                trv = {f.check_id for f in run_trivy(estate) if f.resource == site}
                res = next(r for r in estate.resources if r.address == site)
                floor = {f.rule_id for f in resource_findings(res)}
                units.append(
                    (
                        truth,
                        bool(floor & family.rule_floor),
                        bool(ckv & family.checkov),
                        bool(trv & family.trivy),
                    )
                )
        engines = {
            "rule_floor": [u[1] for u in units],
            "checkov": [u[2] for u in units],
            "trivy": [u[3] for u in units],
        }
        seeded = [i for i, u in enumerate(units) if u[0]]
        clean_units = [i for i, u in enumerate(units) if not u[0]]
        out.append(
            {
                "family": family.key,
                "label": family.label,
                "seeded_defects": len(seeded),
                "clean_resources": len(clean_units),
                "seeded_recall": {
                    name: round(sum(flags[i] for i in seeded) / len(seeded), 3) if seeded else None
                    for name, flags in engines.items()
                },
                "false_positives_on_clean": {
                    name: sum(flags[i] for i in clean_units) for name, flags in engines.items()
                },
                "pairwise": {
                    f"{x}_vs_{y}": agreement(engines[x], engines[y])
                    for x, y in combinations(engines, 2)
                },
            }
        )
    return {"families": out}
