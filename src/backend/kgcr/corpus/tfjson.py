"""Terraform JSON back into :class:`Resource` objects.

The inverse of :meth:`Estate.to_terraform_json`. A ``${type.name.id}`` value becomes a
``__ref__<argument>`` marker plus a reference; ``depends_on`` entries become references.
Only resources come back: the ground-truth intent cannot be recovered from a rendered
document, so callers that need an :class:`Estate` keep the estate itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from kgcr.corpus.resources import Resource

__all__ = ["resources_from_terraform_json"]

_INTERPOLATION = re.compile(r"^\$\{([a-z0-9_]+\.[A-Za-z0-9_\-]+)\.id\}$")


def resources_from_terraform_json(doc: Mapping[str, Any]) -> tuple[Resource, ...]:
    """Every resource in ``doc["resource"]``; raises ``ValueError`` on a malformed document."""
    block = doc.get("resource", {})
    if not isinstance(block, Mapping):
        raise ValueError("'resource' must be a mapping of type to resources")
    resources: list[Resource] = []
    for res_type, by_name in block.items():
        if not isinstance(by_name, Mapping):
            raise ValueError(f"resource type {res_type!r} must map names to bodies")
        for name, body in by_name.items():
            if not isinstance(body, Mapping):
                raise ValueError(f"{res_type}.{name} must be a mapping of arguments")
            resources.append(_resource(str(res_type), str(name), body))
    return tuple(resources)


def _resource(res_type: str, name: str, body: Mapping[str, Any]) -> Resource:
    attributes: dict[str, Any] = {}
    references: list[str] = []
    for key, value in body.items():
        if key == "depends_on":
            references.extend(str(ref) for ref in value)
            continue
        match = _INTERPOLATION.match(value) if isinstance(value, str) else None
        if match:
            attributes[f"__ref__{key}"] = match.group(1)
            references.append(match.group(1))
        else:
            attributes[key] = value
    # A reference can arrive both as an interpolation and in depends_on; keep it once.
    return Resource(res_type, name, attributes, tuple(dict.fromkeys(references)))
