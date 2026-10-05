// Builds presentation/KGCR_Review2.pptx. Every number on a slide is read from a
// committed results file or the CHANGELOG; the speaker notes name the source.
//
//   cd presentation && npm install && node make_deck.js
//
// Rendered copy avoids em dashes and ALL-CAPS labels (house style).

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
// The theme writer ships with the pptx skill, not this repo. Without it the
// scheme colours resolve to Office's stock palette, so say so loudly.
const applyTheme = process.env.PPTX_SKILL_DIR
  ? require(path.join(process.env.PPTX_SKILL_DIR, "scripts", "apply_theme.js")).applyTheme
  : async () => console.warn("PPTX_SKILL_DIR unset: theme colours NOT applied (Office defaults)");

const ROOT = path.resolve(__dirname, "..");
const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const rec = read("results/recommender_report.json");
const adv = read("results/advisor_report.json");
const p8 = read("results/reconstruction_report.json");
const p4 = read("results/p4_df7_checkov_evidence.json");

const THEME = {
  name: "KGCR Review",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A2F", lt1: "FFFFFF", dk2: "123B3A", lt2: "EEF3F2",
    accent1: "1F7A6D", accent2: "C9772A", accent3: "5B6B70",
    accent4: "B23A48", accent5: "7FB8AE", accent6: "C9D6D3",
    hlink: "1F7A6D", folHlink: "5B6B70",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.title = "KGCR Review 2";
pres.author = "Udit Daftary";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "Title dark",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.6,
      fontSize: 40, bold: true, color: C.background1, valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.0, w: 11.7, h: 2.0,
      fontSize: 18, color: C.accent6, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "Content",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.9,
      fontSize: 30, bold: true, color: C.text2, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "KGCR, BCSE355L Review 2", options: { x: 0.6, y: 7.05, w: 6, h: 0.3,
      fontSize: 10, color: C.accent3 } } },
  ],
  slideNumber: { x: 12.2, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.accent3, align: "right" },
});

let section = "";
function slide(master, sec) {
  if (sec !== section) { pres.addSection({ title: sec }); section = sec; }
  return pres.addSlide({ masterName: master, sectionTitle: sec });
}

// Squared status chip: the deck's one repeated motif.
const CHIP = {
  runs: { label: "Runs today", fill: C.accent1 },
  stand: { label: "Local stand-in", fill: C.accent3 },
  rules: { label: "Rule floor only", fill: C.accent2 },
  notrun: { label: "Not run yet", fill: C.accent4 },
  draft: { label: "Draft, in review", fill: C.accent2 },
  authored: { label: "Terraform authored", fill: C.accent3 },
  planned: { label: "Planned", fill: C.accent6 },
  gatepass: { label: "Gate passed", fill: C.accent1 },
  gatefail: { label: "Gate failed", fill: C.accent4 },
  gateinvalid: { label: "Invalid run", fill: C.accent2 },
};
// The sycophancy gate's state comes from the report, so a rebuild after the live
// run shows the real outcome on every slide that mentions it.
const GATE = adv.sycophancy_gate; // NOT_RUN | PASS | FAIL | INVALID
const GATE_CHIP = { NOT_RUN: "notrun", PASS: "gatepass", FAIL: "gatefail", INVALID: "gateinvalid" }[GATE];
const GATE_TEXT = {
  NOT_RUN: "not run yet",
  PASS: "passed",
  FAIL: "failed",
  INVALID: "invalid (no admitted model finding on pass 1)",
}[GATE];
if (!GATE_CHIP) throw new Error(`unknown sycophancy_gate value: ${GATE}`);
function chip(s, kind, x, y, w = 1.7) {
  const k = CHIP[kind];
  s.addText(k.label, {
    x, y, w, h: 0.32, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.05,
    fill: { color: k.fill }, color: kind === "planned" ? C.text1 : C.background1,
    fontSize: 11, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true,
    objectName: `chip-${kind}`,
  });
}
function card(s, x, y, w, h, name) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.background2 },
    line: { color: C.background2 }, objectName: name });
}
function body(s, text, opts) {
  s.addText(text, { fontSize: 15, color: C.text1, valign: "top", isTextBox: true, ...opts });
}
function stat(s, value, label, x, y, w, color = C.accent1) {
  s.addText(value, { x, y, w, h: 0.9, fontSize: 44, bold: true, color, margin: 0, isTextBox: true,
    fontFace: THEME.headFontFace });
  s.addText(label, { x, y: y + 0.9, w, h: 0.8, fontSize: 13, color: C.text1, margin: 0,
    valign: "top", isTextBox: true });
}
const fmt = (v) => v.toFixed(3);
const CHART_TEXT = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  dataLabelFontFace: "+mn-lt", catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent3,
  catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontSize: 12,
  dataLabelColor: HEX.dk1, valGridLine: { style: "none" }, valAxisHidden: true,
  // Headroom past 1.0 so an end label on a full bar sits beside it, not on it.
  catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 1.15 };

// 1. Title
{
  const s = slide("Title dark", "Opening");
  s.addText("Knowledge-graph cloud configuration review", { placeholder: "title" });
  s.addText(
    [
      { text: "Review 2: what runs today, and what does not yet", options: { breakLine: true } },
      { text: "BCSE355L Cloud Architecture Design Project, Dr. Priya V", options: { breakLine: true } },
      { text: "Udit (lead), Manya, Tanmoy   |   github.com/uditdaftary/KGCR_Cloud_Project_2026" },
    ],
    { placeholder: "body" },
  );
  s.addNotes("Frame: recommend and review AWS configurations against regulatory controls, and justify every finding as a traceable path. This review is about implementation progress since Phase-I; every number on the following slides comes from a committed results file.");
}

// 2. Problem
{
  const s = slide("Content", "Problem and gap");
  s.addText("Per-resource checks miss defects in the connections", { placeholder: "title" });
  body(s, [
    { text: "Posture tools see only what is already deployed.", options: { bullet: true, breakLine: true } },
    { text: "Policy-as-code checks one resource at a time.", options: { bullet: true, breakLine: true } },
    { text: "Cost tools are blind to compliance.", options: { bullet: true, breakLine: true } },
    { text: "Nothing reasons over the estate as a graph tied to the controls it must meet.", options: { bullet: true } },
  ], { x: 0.6, y: 1.5, w: 5.6, h: 3.2, paraSpaceAfter: 10 });
  const nodes = ["Internet gateway", "Public subnet", "App host", "Cardholder DB"];
  nodes.forEach((n, i) => {
    const y = 1.5 + i * 1.25;
    s.addText(n, { x: 7.6, y, w: 2.6, h: 0.75, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06,
      fill: { color: i === 3 ? C.accent4 : C.background2 }, color: i === 3 ? C.background1 : C.text1,
      fontSize: 14, bold: true, align: "center", valign: "middle", isTextBox: true, objectName: `node-${i}` });
    s.addText("passes a per-resource scan", { x: 10.4, y: y + 0.15, w: 2.4, h: 0.45, fontSize: 12,
      color: C.accent3, italic: true, isTextBox: true, margin: 0 });
    if (i < 3) s.addShape(pres.shapes.LINE, { x: 8.9, y: y + 0.75, w: 0, h: 0.5,
      line: { color: C.accent3, width: 1.5, endArrowType: "triangle" } });
  });
  body(s, "Every hop is individually compliant; the path from the internet to cardholder data is the defect (DF-7).",
    { x: 0.6, y: 5.0, w: 6.2, h: 1.0, fontSize: 15, italic: true, color: C.accent1 });
  s.addNotes("Source: docs/Project_Report.md section 1 and FD-05 section 5. The right-hand chain is the injected DF-7 'indirect internet reachability' pattern used throughout the results.");
}

// 3. Literature and gap
{
  const s = slide("Content", "Problem and gap");
  s.addText("Fifteen papers agree on what is missing", { placeholder: "title" });
  stat(s, "15", "papers, 2023 to 2026, IEEE, Springer, Elsevier, ACM and MDPI; each record checked against Crossref", 0.6, 1.6, 3.6);
  const findings = [
    ["Measured, not reasoned", "Configuration security is scored after the fact rather than reasoned about before deployment."],
    ["Graphs used reactively", "Graphs appear in incident analysis, not in design or review."],
    ["Two separate graphs", "Compliance knowledge and configuration knowledge are never joined."],
    ["Intent is an input", "Every system takes intent as given; none recovers it from an estate."],
  ];
  findings.forEach(([h, t], i) => {
    const x = 4.7 + (i % 2) * 4.15, y = 1.5 + Math.floor(i / 2) * 2.55;
    card(s, x, y, 3.9, 2.25, `finding-${i}`);
    s.addText(h, { x: x + 0.2, y: y + 0.15, w: 3.5, h: 0.5, fontSize: 18, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    s.addText(t, { x: x + 0.2, y: y + 0.75, w: 3.5, h: 1.35, fontSize: 14, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
  });
  s.addNotes("Source: docs/Literature_Survey.md synthesis, docs/Research_Gap_Udit.md and the two companion gap documents. Each member presents their own five papers.");
}

// 4. Objectives with status
{
  const s = slide("Content", "Plan");
  s.addText("Six objectives, each with a measure and a status", { placeholder: "title" });
  const rows = [
    ["O1", "Encode controls as a queryable graph (L1)", "draft", "6 controls drafted, awaiting human review"],
    ["O2", "Detect multi-hop defects per-resource engines miss", "runs", `graph ${p4.graph_recovered}/${p4.total_df7_estates}, Checkov blind on ${p4.engine_blind}/${p4.total_df7_estates}`],
    ["O3", "Recommend a compliant configuration from intent", "runs", "ranker plus CRITICAL mask; cost not modelled"],
    ["O4", "Reconstruct intent with calibrated confidence", "runs", "per-field accuracy and ECE reported"],
    ["O5", "Explanations as exact reasoning paths", "runs", "template explainer, INV-2 test passes"],
    ["O6", "Governed multi-account AWS with cost controls", "authored", "Terraform written, not applied"],
  ];
  rows.forEach(([id, t, kind, note], i) => {
    const y = 1.45 + i * 0.88;
    s.addText(id, { x: 0.6, y, w: 0.7, h: 0.6, fontSize: 20, bold: true, color: C.accent1, isTextBox: true, margin: 0, valign: "middle", fontFace: THEME.headFontFace });
    s.addText(t, { x: 1.35, y, w: 5.6, h: 0.6, fontSize: 16, color: C.text1, isTextBox: true, margin: 0, valign: "middle" });
    chip(s, kind, 7.1, y + 0.14, 2.0);
    s.addText(note, { x: 9.3, y, w: 3.5, h: 0.6, fontSize: 13, color: C.accent3, isTextBox: true, margin: 0, valign: "middle" });
  });
  s.addNotes("Source: docs/Objectives.md. 'Runs today' means code plus a committed result, on the synthetic corpus. O1 is a draft written by Claude and must be reviewed by Udit before it counts (FD-07 section 2: a model may read L1, never author it).");
}

// 5. Diagram 1
{
  const s = slide("Content", "Architecture");
  s.addText("Diagram 1: AWS cloud architecture (planned)", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "architecture/AWS_Architecture.png"), x: 0.6, y: 1.35, w: 8.9, h: 5.58, objectName: "aws-diagram" });
  chip(s, "planned", 9.9, 1.5, 1.7);
  body(s, [
    { text: "Three accounts, evidence from Config, CloudTrail and cost reports into S3, ETL into the graph store.", options: { bullet: true, breakLine: true } },
    { text: "Cross-account IAM separates read-only harvest from write-only apply.", options: { bullet: true, breakLine: true } },
    { text: "Today: IAM, Budgets, the run bucket and topic exist as Terraform, unapplied; harvest is a local stand-in.", options: { bullet: true } },
  ], { x: 9.9, y: 2.1, w: 2.9, h: 4.6, fontSize: 14, paraSpaceAfter: 8 });
  s.addNotes("Source: architecture/AWS_Architecture.png, generated by architecture/make_diagrams.py. Say first that this is the planning diagram; slide 13 gives the planned-versus-running split.");
}

// 6. Diagram 2
{
  const s = slide("Content", "Architecture");
  s.addText("Diagram 2: complete system flow", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "architecture/System_Architecture.png"), x: 0.6, y: 1.35, w: 7.73, h: 5.58, objectName: "system-diagram" });
  body(s, [
    { text: "Two entry conditions: design from a stated intent, or review an existing estate.", options: { bullet: true, breakLine: true } },
    { text: "The advisor loop is bounded at three passes and never passes a CRITICAL finding silently.", options: { bullet: true, breakLine: true } },
    { text: "Review mode (S1b to S6 here) runs locally today as one command; harvest is a stand-in.", options: { bullet: true } },
  ], { x: 8.8, y: 1.6, w: 4.0, h: 5.0, fontSize: 15, paraSpaceAfter: 10 });
  s.addNotes("Source: architecture/System_Architecture.png and FD-01. The plan, confirm and apply steps (S6 to S10) need live accounts and are not built.");
}

// 7. Dataset
{
  const s = slide("Content", "Data");
  s.addText("The dataset is synthetic, and generated intent-first", { placeholder: "title" });
  stat(s, "180", "estates, one seed family each", 0.6, 1.6, 2.8);
  stat(s, "2,331", "AWS resources, 1,615 dependency edges", 3.6, 1.6, 2.8);
  stat(s, "7", "intent axes carried as ground truth by every estate", 6.6, 1.6, 2.8);
  stat(s, String(adv.rule_floor.seeded_recall["DF-7"].n), "relational (DF-7) defect estates from the injector", 9.6, 1.6, 3.1);
  card(s, 0.6, 4.1, 12.1, 2.0, "dataset-note");
  body(s, [
    { text: "Generated, not downloaded: intent is sampled first, then a clean estate is rendered from it, so each estate carries the intent it was built for.", options: { bullet: true, breakLine: true } },
    { text: "Defects DF-1 to DF-7 are injected into clean estates; the split is estate-level, by seed family, with a leakage guard.", options: { bullet: true, breakLine: true } },
    { text: "No real financial-sector estate is used. Results describe this generator, not production estates.", options: { bullet: true } },
  ], { x: 0.85, y: 4.3, w: 11.6, h: 1.7, paraSpaceAfter: 8 });
  s.addNotes("Source: dataset/dataset_description.md and results/advisor_report.json (DF-7 count over the full injected corpus). Say 'synthetic' before anyone asks.");
}

// 8. What runs
{
  const s = slide("Content", "Implementation");
  s.addText("One command runs review mode end to end", { placeholder: "title" });
  const steps = [
    ["Harvest", "held-out estate from the corpus", "stand"],
    ["Graph", "dependency graph, 3-hop paths", "runs"],
    ["Intent", "P8: per-field value and confidence", "runs"],
    ["Recommend", "P7: ranked options, CRITICAL mask", "runs"],
    ["Advise", "P6: grounded findings, bounded loop", GATE === "NOT_RUN" ? "rules" : "runs"],
    ["Explain", "P9: three audiences, counterfactuals", "runs"],
  ];
  steps.forEach(([h, t, kind], i) => {
    const x = 0.6 + i * 2.05;
    card(s, x, 1.6, 1.85, 2.6, `step-${i}`);
    s.addText(h, { x: x + 0.12, y: 1.75, w: 1.6, h: 0.5, fontSize: 16, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    s.addText(t, { x: x + 0.12, y: 2.3, w: 1.6, h: 1.2, fontSize: 13, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
    chip(s, kind, x + 0.12, 3.65, 1.6);
  });
  s.addText("kgcr review --variant unencrypted_database --audience auditor", { x: 0.6, y: 4.6, w: 12.1, h: 0.55,
    fontFace: "Courier New", fontSize: 16, color: C.background1, fill: { color: C.text2 }, isTextBox: true, margin: 12, valign: "middle" });
  body(s, [
    { text: "Writes the run record, the explanation bundle, the patched spec and three renderings to the artifact store.", options: { bullet: true, breakLine: true } },
    { text: "155 tests; ruff, ruff format, mypy (strict) and pytest all pass with PYTHONHASHSEED=0.", options: { bullet: true, breakLine: true } },
    { text: GATE === "NOT_RUN"
        ? "The advisor's LLM path is built and tested offline; its live run waits on an API key."
        : `The advisor's LLM path ran live (${adv.llm.model_calls} recorded calls); sycophancy gate ${GATE_TEXT}.`, options: { bullet: true } },
  ], { x: 0.6, y: 5.35, w: 12.1, h: 1.6, paraSpaceAfter: 6 });
  s.addNotes("Source: src/backend/kgcr/orchestration/review.py and cli.py. Rule floor only means the advisor ran its deterministic rules; relational and resilience findings need the Gemini path, which has not run live.");
}

// 9. Recommender result
{
  const s = slide("Content", "Results");
  s.addText("Recommender: right option set for 23 of 24 estates", { placeholder: "title" });
  const R = rec.rankers;
  const names = ["Popularity", "Per-archetype", "Model, true intent", "Model, reconstructed intent"];
  const keys = ["popularity", "archetype_frequency", "model_true_intent", "model_reconstructed_intent"];
  s.addChart(pres.charts.BAR, [{ name: "Exact option set", labels: names, values: keys.map((k) => R[k].exact_set) }], {
    x: 0.6, y: 1.4, w: 7.4, h: 5.3, barDir: "bar", chartColors: [HEX.accent1], showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", showTitle: true, title: "Exact option-set recovery, held-out split (n = 24)",
    titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt", ...CHART_TEXT,
  });
  body(s, [
    { text: `R-precision: popularity ${fmt(R.popularity.r_precision)}, per-archetype ${fmt(R.archetype_frequency.r_precision)}, model ${fmt(R.model_true_intent.r_precision)}.`, options: { bullet: true, breakLine: true } },
    { text: "Not a GNN: the generator is a function of intent, so a random forest already saturates and a GNN has no headroom to show.", options: { bullet: true, breakLine: true } },
    { text: `The CRITICAL mask removed the one illegal option in the pool (${rec.masked_critical[0].join(" ")}), even when forced to rank first.`, options: { bullet: true } },
  ], { x: 8.3, y: 1.6, w: 4.5, h: 5.0, fontSize: 14, paraSpaceAfter: 10 });
  s.addNotes("Source: results/recommender_report.json. Options are (resource type, attribute, value) with identity attributes excluded. This measures recovery of the generator's mapping, not real-world recommendation quality.");
}

// 10. Advisor and relational detection
{
  const s = slide("Content", "Results");
  s.addText("Advisor: rules catch properties, the graph catches paths", { placeholder: "title" });
  const sr = adv.rule_floor.seeded_recall;
  stat(s, `${p4.graph_recovered}/${p4.total_df7_estates}`, "relational paths recovered by the graph", 0.6, 1.6, 3.0);
  stat(s, `${p4.engine_blind}/${p4.total_df7_estates}`, "where Checkov's sink verdict matches the clean parent", 3.8, 1.6, 3.0, C.accent4);
  stat(s, fmt(sr["DF-2"].recall), "rule-floor recall, DF-1 to DF-4 (holds by construction)", 7.0, 1.6, 2.8, C.accent3);
  stat(s, fmt(sr["DF-7"].recall), `rule-floor recall on DF-7 (n = ${sr["DF-7"].n})`, 10.0, 1.6, 2.7, C.accent3);
  card(s, 0.6, 3.9, 12.1, 2.3, "gate-card");
  chip(s, GATE_CHIP, 0.85, 4.1, 2.0);
  s.addText("Sycophancy gate (the roadmap's hard gate)", { x: 3.05, y: 4.07, w: 9.4, h: 0.4, fontSize: 17, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
  body(s, [
    { text: "Same non-compliant spec, three passes, rising pressure to withdraw findings. Pass requires 100% of the model's own findings to persist.", options: { bullet: true, breakLine: true } },
    { text: "Enforcement is tested offline: a scripted model that caves fails the gate, while carry-forward keeps the system's findings.", options: { bullet: true, breakLine: true } },
    { text: GATE === "NOT_RUN"
        ? "The live result needs a Gemini API key; it has not run, and no result is claimed."
        : `Live result: ${GATE_TEXT}. Per-trial raw persistence is in results/advisor_report.json.`, options: { bullet: true } },
  ], { x: 0.85, y: 4.6, w: 11.6, h: 1.5, fontSize: 14, paraSpaceAfter: 6 });
  s.addNotes("Sources: results/p4_df7_checkov_evidence.json (graph versus Checkov) and results/advisor_report.json (rule floor). DF-1 to DF-4 recall is 1.0 by construction because the injectors produce exactly what the rules check; it is a sanity floor, not a benchmark.");
}

// 11. Intent reconstruction + explainer
{
  const s = slide("Content", "Results");
  s.addText("Intent reconstruction is honest about what it cannot see", { placeholder: "title" });
  const pf = p8.report.per_field;
  const fields = Object.keys(pf).sort();
  s.addChart(pres.charts.BAR, [{ name: "Accuracy", labels: fields.map((f) => f.replace("_", " ")), values: fields.map((f) => pf[f].accuracy) }], {
    x: 0.6, y: 1.4, w: 7.4, h: 5.3, barDir: "bar", chartColors: [HEX.accent1], showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", showTitle: true, title: "Per-field accuracy on the held-out split",
    titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt", ...CHART_TEXT,
  });
  body(s, [
    { text: `iam shape: accuracy ${fmt(pf.iam_shape.accuracy)} with ECE ${fmt(pf.iam_shape.expected_calibration_error)}. The generator leaves no structural trace, and the model is confidently wrong.`, options: { bullet: true, breakLine: true } },
    { text: "Low-confidence fields are escalated to the user, never silently assumed.", options: { bullet: true, breakLine: true } },
    { text: "Explainer: every finding carries its exact path, control and tested counterfactual. The three audience renderings yield identical claim sets (INV-2) for every defect variant.", options: { bullet: true } },
  ], { x: 8.3, y: 1.6, w: 4.5, h: 5.0, fontSize: 14, paraSpaceAfter: 10 });
  s.addNotes("Sources: results/reconstruction_report.json; INV-2 is tests/explainer/test_explainer.py, which extracts claims back out of the rendered text. Cost deltas in explanations are stated as not modelled.");
}

// 12. Demo
{
  const s = slide("Content", "Results");
  s.addText("Demo: a cardholder database without encryption", { placeholder: "title" });
  // Verbatim CLI lines from a real run; "..." marks an elision, nothing is reworded.
  const out = [
    "[1/6] harvest   local stand-in for AWS Config (no AWS call)",
    "      estate fd6f7a9427c6ffa4, held-out split, 17 resources",
    "      injected for the demo: unencrypted_database (DF-2)",
    "[3/6] intent    archetype=payments_api, az_spread=three_az, ...",
    "      low confidence, confirm with the user: iam_shape",
    "[4/6] recommend ...",
    "      recommended, not in estate: ('aws_db_instance', 'storage_encrypted', 'True')",
    "[5/6] advise    LLM: disabled; loop CONVERGED (CLEAN) after 2 pass(es)",
    "      [CRITICAL] kg://control/pci-dss-v4/3.5.1 on aws_db_instance.cardholder (rule)",
  ].join("\n");
  s.addText(out, { x: 0.6, y: 1.4, w: 12.1, h: 2.75, fontFace: "Courier New", fontSize: 13, color: C.background1,
    fill: { color: C.text2 }, isTextBox: true, margin: 12, valign: "middle" });
  s.addText("From the stored auditor explanation (explanation_auditor.md):", { x: 0.6, y: 4.3, w: 12.1, h: 0.35,
    fontSize: 12, italic: true, color: C.accent3, isTextBox: true, margin: 0 });
  s.addText("Remediation tested: align aws_db_instance.cardholder with the compliant template. Outcome: RESOLVED; single-resource rules pass after the change.",
    { x: 0.6, y: 4.68, w: 12.1, h: 0.75, fontFace: "Courier New", fontSize: 13, color: C.text1,
      fill: { color: C.background2 }, isTextBox: true, margin: 12, valign: "middle" });
  body(s, [
    { text: "The recommender and the advisor flag the same setting independently, from different inputs.", options: { bullet: true, breakLine: true } },
    { text: "Without the LLM, a DF-7 run finds nothing; its stored explanation says so in a scope note.", options: { bullet: true } },
  ], { x: 0.6, y: 5.6, w: 12.1, h: 1.2, paraSpaceAfter: 6 });
  s.addNotes("Live command: kgcr review --variant unencrypted_database --audience auditor. Output trimmed for the slide; run it live if time allows (about 15 seconds). PCI-DSS v4.0 3.5.1 covers stored PAN; 3.4 is display masking.");
}

// 13. AWS plan versus running
{
  const s = slide("Content", "Cloud");
  s.addText("AWS services: planned versus running", { placeholder: "title" });
  const cols = [
    ["stand", "Runs locally today", ["S3 run bucket: local directory by default", "SNS: logged notification by default", "Config harvest: synthetic corpus", "SageMaker: local scikit-learn", "Bedrock: Gemini Flash (free tier), fixture replay"]],
    ["authored", "Written, not applied", ["Cross-account IAM roles (harvest and apply)", "AWS Budgets alarms at 5, 15 and 30 USD", "S3 run bucket and SNS topic, adapters tested on mocked AWS", "Least-privilege publish policy"]],
    ["planned", "Planned for Phase-II", ["EC2 and Neo4j graph store", "Lambda and Glue ETL", "API Gateway and Cognito", "CloudTrail, CloudWatch, EventBridge", "KMS, VPC topology, Organizations"]],
  ];
  cols.forEach(([kind, h, items], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.5, 3.85, 5.2, `aws-col-${i}`);
    chip(s, kind, x + 0.2, 1.7, 2.2);
    s.addText(h, { x: x + 0.2, y: 2.15, w: 3.45, h: 0.6, fontSize: 17, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    body(s, items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
      { x: x + 0.2, y: 2.85, w: 3.45, h: 3.7, fontSize: 14, paraSpaceAfter: 8 });
  });
  s.addNotes("Source: docs/Project_Report.md section 8, the 21-service planning table. Nothing has been deployed and no AWS money has been spent. The pipeline talks to storage and notification only through two small interfaces, so AWS-backed versions slot in without changing it.");
}

// 14. Close
{
  const s = slide("Title dark", "Close");
  s.addText("Limits, and what comes next", { placeholder: "title" });
  s.addText([
    { text: `Limits: synthetic corpus; draft L1 awaiting review; sycophancy gate ${GATE_TEXT}; no cost model.`, options: { breakLine: true } },
    { text: `Next: ${GATE === "NOT_RUN" ? "run the sycophancy gate live, " : ""}review and verify L1, validate and apply the Terraform in a sandbox.`, options: { breakLine: true } },
    { text: "Then: gold set (P2), live AWS harvest, and the human study." },
  ], { placeholder: "body" });
  s.addNotes("Close on the honest split. Code in this repository is authored by Udit with Claude's assistance; Manya and Tanmoy own their literature and research-gap sections.");
}

(async () => {
  const out = path.join(__dirname, "KGCR_Review2.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log(`wrote ${out}`);
})();
