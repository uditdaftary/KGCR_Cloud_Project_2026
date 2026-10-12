"""Build ``results/dashboard.html``: a self-contained view over the ``results/*.json`` reports.

    python src/frontend/build_dashboard.py [--runs runs-local/runs]

Everything on the page is read from the reports, so a gate that has not run says so and the
page changes by itself once ``run_advisor.py`` records a live result. No JavaScript, no
external assets: the file opens offline and can be attached to the submission.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"

CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--mute:#78716c;--line:#e7e5e4;--card:#fff;--ok:#15803d;--bad:#b91c1c;--warn:#a16207;--bar:#44403c;--bar2:#a8a29e}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#e7e5e4;--mute:#a8a29e;--line:#2b2927;--card:#1c1b19;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--bar:#d6d3d1;--bar2:#57534e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;margin:0 0 12px}.sub{color:var(--mute);margin:0 0 24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}
@media (max-width:480px){.grid{grid-template-columns:1fr}}
section{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px}
.row{display:grid;grid-template-columns:150px 1fr 56px;gap:8px;align-items:center;margin:6px 0;font-size:13px}
.track{height:8px;background:var(--bar2);border-radius:2px;position:relative}.fill{height:8px;background:var(--bar);border-radius:2px}
.num{text-align:right;font-variant-numeric:tabular-nums}.mute{color:var(--mute)}
.gate{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:16px}.gate>div{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:12px 16px;min-width:200px}
.big{font-size:20px;font-weight:600}.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:500}.note{font-size:12px;color:var(--mute);margin-top:10px}
"""


def load(name: str) -> dict[str, Any]:
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def bars(items: list[tuple[str, float, str]], scale: float = 1.0) -> str:
    return "".join(
        f'<div class="row"><span>{escape(label)}</span><div class="track">'
        f'<div class="fill" style="width:{max(0.0, min(value / scale, 1.0)) * 100:.1f}%"></div></div>'
        f'<span class="num">{escape(text)}</span></div>'
        for label, value, text in items
    )


def gate_tile(title: str, value: str, detail: str) -> str:
    tone = {"PASS": "ok", "FAIL": "bad", "INVALID": "bad", "NOT_RUN": "warn"}.get(value, "")
    shown = "not run" if value == "NOT_RUN" else value.lower()
    return (
        f'<div><div class="mute">{escape(title)}</div>'
        f'<div class="big {tone}">{escape(shown)}</div><div class="note">{escape(detail)}</div></div>'
    )


def advisor_section(rep: dict[str, Any]) -> str:
    recall = rep.get("rule_floor", {}).get("seeded_recall", {})
    out = bars([(k, v["recall"], f'{v["recall"]:.2f}') for k, v in sorted(recall.items())])
    out += (
        '<p class="note">Rule floor only. DF-1 to DF-4 are 1.00 by construction (the injectors '
        "produce exactly what the rules check). DF-5 to DF-7 need the LLM advisor.</p>"
    )
    llm = rep.get("llm")
    if isinstance(llm, dict):
        beyond = llm.get("seeded_recall_beyond_rule_floor") or {}
        out += "<h2 style='margin-top:16px'>With the LLM advisor</h2>" + bars(
            [
                (k, float(v), f"{float(v):.2f}")
                for k, v in sorted(beyond.items())
                if isinstance(v, int | float)
            ]
        )
        out += (
            f'<p class="note">{llm.get("model_calls")} model calls, grounding rate '
            f'{llm.get("grounding_rate")}, critical findings on clean estates '
            f'{llm.get("clean_critical_findings")} of {llm.get("clean_estates")}.</p>'
        )
    return out


def reconstruction_section(rep: dict[str, Any]) -> str:
    fields = rep.get("report", {}).get("per_field", {})
    rows = "".join(
        f'<tr><td>{escape(name)}</td><td class="num">{f["accuracy"]:.3f}</td>'
        f'<td class="num">{f["expected_calibration_error"]:.3f}</td><td class="num">{f["n"]}</td></tr>'
        for name, f in sorted(fields.items())
    )
    return (
        "<table><tr><th>Field</th><th>Accuracy</th><th>ECE</th><th>n</th></tr>"
        f"{rows}</table>"
        '<p class="note">Held-out estates. iam_shape is the weak axis and is poorly calibrated '
        "(high ECE); the reconstructor escalates rather than guessing when confidence is low.</p>"
    )


def recommender_section(rep: dict[str, Any]) -> str:
    rankers = rep.get("rankers", {})
    out = ""
    for metric in ("exact_set", "r_precision"):
        out += f'<h2 style="margin-top:8px">{metric.replace("_", " ")}</h2>' + bars(
            [
                (k.replace("_", " "), v[metric], f"{v[metric]:.2f}")
                for k, v in sorted(rankers.items())
            ]
        )
    out += (
        f'<p class="note">{rep.get("n_test")} held-out estates, {rep.get("n_candidates")} candidate '
        f'options; {len(rep.get("masked_critical", []))} critical option hard-masked, '
        f'{len(rep.get("flagged_noncritical", []))} flagged.</p>'
    )
    return out


def sycophancy_section(rep: dict[str, Any]) -> str:
    verdict = str(rep.get("sycophancy_gate", "NOT_RUN"))
    if verdict == "NOT_RUN":
        return '<p class="mute">No live model call has been made, so no result is claimed.</p>'
    rows = "".join(
        f'<tr><td>{escape(str(t.get("variant", "")))}</td><td>{escape(str(t.get("valid", "")))}</td>'
        f'<td class="num">{escape(str(t.get("raw_persistence", "")))}</td></tr>'
        for t in rep.get("sycophancy_trials", [])
    )
    return f"<table><tr><th>Variant</th><th>Valid</th><th>Raw persistence</th></tr>{rows}</table>"


def latest_review(runs: Path) -> str:
    bundles = sorted(runs.glob("*/bundle.json"), key=lambda p: p.stat().st_mtime)
    if not bundles:
        return '<p class="mute">No review run found. Try <code>kgcr review</code>.</p>'
    b = json.loads(bundles[-1].read_text(encoding="utf-8"))
    rows = "".join(
        f'<tr><td>{escape(f["severity"])}</td><td>{escape(f["control_ref"])}</td>'
        f'<td>{escape(f["assertion"])}</td><td>{escape(", ".join(f["affected_elements"]))}</td>'
        f'<td>{escape(f["counterfactual"]["outcome"] if f.get("counterfactual") else "n/a")}</td></tr>'
        for f in b.get("findings", [])
    )
    return (
        f'<p class="note">Estate {escape(b["estate_id"])}, loop {escape(b["loop_status"])} '
        f'({escape(b["loop_reason"])}). {escape(b.get("scope_note", ""))}</p>'
        "<table><tr><th>Severity</th><th>Control</th><th>Finding</th><th>Resources</th>"
        f"<th>Counterfactual</th></tr>{rows}</table>"
        '<p class="note">Control texts are drafts pending review.</p>'
    )


def build(runs: Path) -> str:
    adv, rec, recon = (
        load("advisor_report.json"),
        load("recommender_report.json"),
        load("reconstruction_report.json"),
    )
    gate = str(adv.get("sycophancy_gate", "NOT_RUN"))
    llm_state = "NOT_RUN" if adv.get("llm") == "NOT_RUN" else "ok"
    overall = recon.get("report", {}).get("overall_accuracy")
    tiles = (
        gate_tile("Sycophancy gate", gate, "Advisor must keep every valid finding under pushback")
        + gate_tile("LLM advisor", llm_state, "Gemini path behind an admission filter")
        + gate_tile(
            "Intent reconstruction",
            f"{overall:.3f}" if overall is not None else "NOT_RUN",
            "Overall held-out accuracy",
        )
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>KGCR results</title><style>{CSS}</style></head><body><main>
<h1>KGCR results</h1><p class="sub">Synthetic, self-generated corpus. Read from results/*.json; nothing here is a real estate.</p>
<div class="gate">{tiles}</div>
<div class="grid">
<section><h2>Advisor: seeded-defect recall</h2>{advisor_section(adv)}</section>
<section><h2>Advisor: sycophancy trials</h2>{sycophancy_section(adv)}</section>
<section><h2>Intent reconstruction</h2>{reconstruction_section(recon)}</section>
<section><h2>Recommender versus baselines</h2>{recommender_section(rec)}</section>
</div>
<section style="margin-top:16px"><h2>Latest review run</h2>{latest_review(runs)}</section>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=ROOT / "runs-local" / "runs")
    parser.add_argument("--out", type=Path, default=RESULTS / "dashboard.html")
    args = parser.parse_args()
    args.out.write_text(build(args.runs), encoding="utf-8")
    print(f"dashboard: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
