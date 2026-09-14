"""An estate: a rendered set of resources plus the intent that produced it.

The :class:`Estate` is the unit of the corpus. It carries its originating
:class:`~kgcr.corpus.intent.Intent` as ground truth (FD-05 §8) and a
``seed_family`` used by the estate-level split to keep structurally similar
estates on the same side of the train/test boundary (FD-05 §9).

``to_terraform_json`` emits Terraform's JSON configuration syntax (``.tf.json``)
— valid input to ``terraform plan`` and to the Phase 4 policy engines — with
references rendered as HCL interpolation strings so terraform resolves the
dependency graph the same way the internal IR does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kgcr.corpus.intent import Intent
from kgcr.corpus.resources import Resource

__all__ = ["Estate"]


def _interpolate(reference_address: str) -> str:
    """Render a resource address as an HCL interpolation of its ``id``."""
    return "${" + f"{reference_address}.id" + "}"


@dataclass(frozen=True, slots=True)
class Estate:
    """A synthetic estate and the intent it was generated from."""

    estate_id: str
    intent: Intent
    resources: tuple[Resource, ...]
    seed: int
    seed_family: str
    region: str

    @property
    def resource_addresses(self) -> tuple[str, ...]:
        return tuple(r.address for r in self.resources)

    def to_terraform_json(self) -> dict[str, Any]:
        """Render valid Terraform JSON configuration syntax.

        References become ``${type.name.id}`` interpolations, injected into each
        resource block under the argument the generator recorded them on (kept
        in ``attributes`` as a ``__ref__<arg>`` marker), or appended as a
        ``depends_on`` when the reference is structural rather than an argument.
        """
        resource_block: dict[str, dict[str, Any]] = {}
        for res in self.resources:
            body = _render_resource_body(res)
            resource_block.setdefault(res.type, {})[res.name] = body

        return {
            "terraform": {
                "required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.60"}}
            },
            "provider": {"aws": {"region": self.region}},
            "resource": resource_block,
        }

    def to_dict(self) -> dict[str, Any]:
        """Full serialisation including the ground-truth intent."""
        return {
            "estate_id": self.estate_id,
            "seed": self.seed,
            "seed_family": self.seed_family,
            "region": self.region,
            "intent": self.intent.to_dict(),
            "resources": [r.to_dict() for r in self.resources],
        }


def _render_resource_body(res: Resource) -> dict[str, Any]:
    """Turn a Resource into a Terraform JSON resource body.

    Attributes prefixed ``__ref__`` name an argument that should carry an
    interpolation to a referenced resource (e.g. ``__ref__vpc_id`` ->
    ``vpc_id = "${aws_vpc.main.id}"``). Any references not consumed that way are
    emitted as ``depends_on`` so the dependency still appears in the plan graph.
    """
    body: dict[str, Any] = {}
    consumed: set[str] = set()

    for key, value in res.attributes.items():
        if key.startswith("__ref__"):
            arg = key[len("__ref__") :]
            body[arg] = _interpolate(str(value))
            consumed.add(str(value))
        else:
            body[key] = value

    remaining = [ref for ref in res.references if ref not in consumed]
    if remaining:
        body["depends_on"] = [f"{ref}" for ref in remaining]

    return body
