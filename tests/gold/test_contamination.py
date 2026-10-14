"""The gold set never reaches training: no module that fits, generates or reviews imports it.

FD-05 4C: contaminating the gold set destroys both its jobs at once and cannot be undone, so
the guarantee is structural and checked here, not a convention.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "backend" / "kgcr"
# Only the dashboard (which hosts the register) and the gold package itself may name it.
ALLOWED = {"dashboard", "gold"}


def _imports_gold(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            continue
        if any(n == "kgcr.gold" or n.startswith("kgcr.gold.") for n in names):
            return True
    return False


def test_no_training_generation_or_review_module_imports_the_gold_set() -> None:
    offenders = [
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if path.relative_to(PACKAGE).parts[0] not in ALLOWED and _imports_gold(path)
    ]
    assert offenders == []


def test_the_entry_points_that_fit_models_do_not_import_it_either() -> None:
    offenders = [p.name for p in (ROOT / "src" / "ml_model").glob("*.py") if _imports_gold(p)]
    assert offenders == []


def test_the_guard_can_fail() -> None:
    # A scan that cannot fail proves nothing: the dashboard does import it.
    assert _imports_gold(PACKAGE / "dashboard" / "authoring.py")
