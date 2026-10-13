"""Terraform HCL into :class:`Resource` objects, for configurations we did not write.

``bc-python-hcl2`` (Checkov's parser, imported as ``hcl2``) wraps every attribute value in a
one-element list and every block in a list of dicts. This unwraps exactly that one layer, so a
list-valued attribute such as ``cidr_blocks = ["0.0.0.0/0"]`` stays a list, and keeps
``ingress`` and ``egress`` as lists of rule dicts even when there is a single block.

Expressions the parser cannot resolve (``${var.x}``, ``${local.y}``) are kept as strings and
counted, because the rule floor reads literal values only: an unresolved expression is a
blind spot to report, not a pass.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kgcr.corpus.resources import Resource

__all__ = ["ParsedDirectory", "load_hcl_directory", "unresolved_attributes"]

logger = logging.getLogger(__name__)

_BLOCK_LISTS = frozenset({"ingress", "egress"})
_PARSER_META = frozenset({"__start_line__", "__end_line__"})


@dataclass(frozen=True, slots=True)
class ParsedDirectory:
    directory: Path
    files: int
    resources: tuple[Resource, ...]
    skipped: tuple[str, ...]  # files the parser could not read, with why


def _unwrap(name: str, raw: Any) -> Any:
    value = raw[0] if isinstance(raw, list) and len(raw) == 1 else raw
    if isinstance(value, dict):
        value = {k: _unwrap(k, v) for k, v in value.items() if k not in _PARSER_META}
    elif isinstance(value, list):
        value = [
            {k: _unwrap(k, v) for k, v in item.items() if k not in _PARSER_META}
            if isinstance(item, dict)
            else item
            for item in value
        ]
    if name in _BLOCK_LISTS and isinstance(value, dict):
        value = [value]
    return value


def unresolved_attributes(res: Resource, names: frozenset[str]) -> list[str]:
    """Which of ``names`` hold an expression the parser left unresolved."""
    return [
        n
        for n in names
        if isinstance(res.attributes.get(n), str) and "${" in str(res.attributes[n])
    ]


def load_hcl_directory(directory: Path) -> ParsedDirectory:
    """Every ``aws_*`` resource in the ``*.tf`` files directly inside ``directory``."""
    hcl2: Any = importlib.import_module("hcl2")  # untyped third-party parser

    resources: list[Resource] = []
    skipped: list[str] = []
    files = sorted(directory.glob("*.tf"))
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                doc = hcl2.load(fh)
        except Exception as exc:  # a third-party file the parser rejects is reported, not fatal
            logger.warning("skipping %s: %s", path, exc)
            skipped.append(f"{path.name}: {type(exc).__name__}")
            continue
        for block in doc.get("resource", []):
            for res_type, named in block.items():
                if not str(res_type).startswith("aws_"):
                    continue
                for name, body in named.items():
                    attrs = {k: _unwrap(k, v) for k, v in body.items() if k not in _PARSER_META}
                    resources.append(Resource(str(res_type), str(name), attrs))
    return ParsedDirectory(directory, len(files), tuple(resources), tuple(skipped))
