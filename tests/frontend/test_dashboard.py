import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "src" / "frontend" / "build_dashboard.py"


def test_dashboard_reports_unrun_gate_and_escapes(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("build_dashboard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    html = module.build(tmp_path)  # no runs under tmp_path
    assert "not run" in html and "No review run found" in html
    assert "<script" not in html
