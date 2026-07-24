"""The estate intermediate representation: typed resources and references.

A :class:`Resource` is one Terraform-managed resource, addressed ``type.name``
(the Terraform convention). ``attributes`` holds constant argument values;
``references`` names other resources this one depends on, by address.

This IR is deliberately provider-shaped (types are real ``aws_*`` types,
attributes are real argument names) so it renders straight to Terraform JSON and
so a graph built from it matches the graph a real ``terraform show -json`` plan
would yield.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Resource"]


@dataclass(frozen=True, slots=True)
class Resource:
    """A single Terraform resource in an estate."""

    type: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    # Addresses (``type.name``) of resources this one references.
    references: tuple[str, ...] = ()

    @property
    def address(self) -> str:
        return f"{self.type}.{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "type": self.type,
            "name": self.name,
            "attributes": dict(self.attributes),
            "references": list(self.references),
        }
