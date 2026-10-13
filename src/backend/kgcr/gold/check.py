"""The Phase 1 to 2 acceptance check (FD-07 section 12) over one gold configuration.

Every gold configuration is compliant by construction, so any CRITICAL the rule floor raises
on one is either a false positive or an L1 encoding error. The check covers single-resource
rules only; relational checks need the dependency graph and are not claimed here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from kgcr.corpus.tfjson import resources_from_terraform_json
from kgcr.defects.detectors import resource_findings
from kgcr.defects.taxonomy import DEFAULT_CONTROL, DEFAULT_SEVERITY

__all__ = ["GoldCheck", "check_config"]


@dataclass(frozen=True, slots=True)
class GoldCheck:
    resources: int
    findings: tuple[dict[str, str], ...]

    @property
    def criticals(self) -> tuple[dict[str, str], ...]:
        return tuple(f for f in self.findings if f["severity"] == "CRITICAL")

    def to_dict(self) -> dict[str, Any]:
        return {
            "resources": self.resources,
            "findings": list(self.findings),
            "criticals": list(self.criticals),
            "scope": "single-resource rules only",
        }


def check_config(doc: Mapping[str, Any]) -> GoldCheck:
    """Run the single-resource rule floor over ``doc``; ``ValueError`` if it is not a config."""
    resources = resources_from_terraform_json(doc)
    if not resources:
        raise ValueError("the configuration holds no resources")
    findings = tuple(
        {
            "address": res.address,
            "rule": f.rule_id,
            "control": DEFAULT_CONTROL[f.defect_class],
            "severity": DEFAULT_SEVERITY[f.defect_class].value,
            "message": f.message,
        }
        for res in resources
        for f in resource_findings(res)
    )
    return GoldCheck(len(resources), findings)
