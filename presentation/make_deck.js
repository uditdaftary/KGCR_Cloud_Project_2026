// Builds presentation/KGCR_Final.pptx, the final-review deck. KGCR_Review2.pptx is a frozen
// earlier deck and is never written by this script.
//
//   cd presentation && npm install
//   NODE_PATH="$PWD/node_modules" PPTX_SKILL_DIR=<pptx skill dir> node make_deck.js
//
// Every number on a results slide is read from a committed results file when the deck is
// built; the speaker notes name the source and carry the caveats the slides leave out.
// Dashboard screenshots are tiles in presentation/screenshots/tiles (2400x1350 crops of the
// live dashboard). The terminal slides hold empty frames: the screenshots are pasted in by
// hand, following CLI_RUNBOOK.md.
// Rendered copy avoids em dashes and ALL-CAPS labels (house style).

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
// The theme writer ships with the pptx skill, not this repo. Without it the scheme colours
// resolve to Office's stock palette, so say so loudly.
const applyTheme = process.env.PPTX_SKILL_DIR
  ? require(path.join(process.env.PPTX_SKILL_DIR, "scripts", "apply_theme.js")).applyTheme
  : async () => console.warn("PPTX_SKILL_DIR unset: theme colours NOT applied (Office defaults)");

const ROOT = path.resolve(__dirname, "..");
const TILES = path.join(__dirname, "screenshots", "tiles");
const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const rec = read("results/recommender_report.json");
const adv = read("results/advisor_report.json");
const p8 = read("results/reconstruction_report.json");
const p4 = read("results/p4_df7_checkov_evidence.json");
const exp = read("results/explainer_report.json");
const cd = read("results/corpus_d_report.json");
const gnn = read("results/gnn_ablation.json");

const THEME = {
  name: "KGCR Final",
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
pres.title = "KGCR Final Review";
pres.author = "Udit Daftary, Manya, Tanmoy";
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
    { text: { text: "KGCR, BCSE355L final review", options: { x: 0.6, y: 7.05, w: 6, h: 0.3,
      fontSize: 10, color: C.accent3 } } },
  ],
  slideNumber: { x: 12.2, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.accent3, align: "right" },
});
// Dark stage for dashboard screenshots: the dashboard itself is dark, so a dark slide lets it
// sit on the page rather than float on white.
pres.defineSlideMaster({
  title: "Shot",
  background: { color: C.text2 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 12.1, h: 0.85,
      fontSize: 28, bold: true, color: C.background1, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "KGCR, BCSE355L final review", options: { x: 0.6, y: 7.05, w: 6, h: 0.3,
      fontSize: 10, color: C.accent5 } } },
  ],
  slideNumber: { x: 12.2, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
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
  draft: { label: "Draft, in review", fill: C.accent2 },
  authored: { label: "Terraform authored", fill: C.accent3 },
  planned: { label: "Planned", fill: C.accent6 },
  gatepass: { label: "Gate passed", fill: C.accent1 },
};
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
const bullets = (items) => items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
const fmt = (v) => v.toFixed(3);
const CHART_TEXT = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  dataLabelFontFace: "+mn-lt", catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent3,
  catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontSize: 12,
  dataLabelColor: HEX.dk1, valGridLine: { style: "none" }, valAxisHidden: true,
  // Headroom past 1.0 so an end label on a full bar sits beside it, not on it.
  catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 1.15 };

// The sycophancy gate's state comes from the report, so a rebuild after a new live run cannot
// leave a stale "passed" on the slide.
const GATE = adv.sycophancy_gate;
if (GATE !== "PASS") throw new Error(`the deck brags that the sycophancy gate passed; the report says ${GATE}`);
const validTrials = adv.sycophancy_trials.filter((t) => t.valid).length;
const beyondRules = Object.values(adv.llm.seeded_recall_beyond_rule_floor).filter(Boolean).length;
const goatResources = cd.repositories.cloudgoat.aws_resources + cd.repositories.terragoat.aws_resources;

// ---- screenshot slides --------------------------------------------------------------

function shot(sec, title, tile, captions, notes) {
  const s = slide("Shot", sec);
  s.addText(title, { placeholder: "title" });
  const img = path.join(TILES, `${tile}.png`);
  if (!fs.existsSync(img)) throw new Error(`missing screenshot tile ${img}`);
  // 2400x1350 tile at 10 in wide is 5.625 in tall.
  s.addImage({ path: img, x: 0.6, y: 1.3, w: 10.0, h: 5.625, objectName: `shot-${tile}`,
    line: { color: HEX.accent3, width: 0.75 } });
  s.addText(bullets(captions), { x: 10.85, y: 1.3, w: 1.9, h: 5.6, fontSize: 12, color: C.accent6,
    valign: "top", isTextBox: true, margin: 0, paraSpaceAfter: 10 });
  s.addNotes(notes);
}

// ---- terminal slides: empty frames to paste screenshots into -----------------------------

// frames: heights in inches, stacked. Heights follow the expected line count of the output
// (about 0.2 in a line), so a pasted screenshot fills its frame without being rescaled.
function cli(title, frames, boast, notes) {
  const s = slide("Content", "Terminal");
  s.addText(title, { placeholder: "title" });
  if (boast.length) {
    s.addText(boast.join(" "), { x: 0.6, y: 1.1, w: 12.1, h: 0.45, fontSize: 14, italic: true,
      color: C.accent1, valign: "middle", isTextBox: true, margin: 0 });
  }
  // Space below the subtitle: 1.7 to 6.95 in. Scale the frames down if they would overflow.
  const GAP = 0.15, AVAIL = 5.25;
  const total = frames.reduce((a, h) => a + h, 0) + GAP * (frames.length - 1);
  const k = total > AVAIL ? (AVAIL - GAP * (frames.length - 1)) / (total - GAP * (frames.length - 1)) : 1;
  let y = 1.7;
  frames.forEach((h, i) => {
    const hh = +(h * k).toFixed(2);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 12.1, h: hh, fill: { color: "0B0F10" },
      line: { color: HEX.accent5, width: 1.25, dashType: "dash" }, objectName: `terminal-frame-${i + 1}` });
    y += hh + GAP;
  });
  s.addNotes(notes);
}

// 1. Title
{
  const s = slide("Title dark", "Opening");
  s.addText("KGCR: the cloud reviewer that sees what scanners cannot", { placeholder: "title" });
  s.addText(
    [
      { text: "Our final presentation for the BCSE355L Cloud Architecture Design Project, Dr. Priya V", options: { breakLine: true } },
      { text: "Udit (lead), Manya, Tanmoy   |   github.com/uditdaftary/KGCR_Cloud_Project_2026" },
    ],
    { placeholder: "body" },
  );
  s.addNotes("Frame: we built a system that reviews and designs AWS configurations over a knowledge graph and justifies every finding as a traceable path. Every number on the results slides is read from a committed results file. Code in this repository is Udit's, written with Claude's assistance; Manya and Tanmoy own their literature and research-gap sections.");
}

// 2. Problem
{
  const s = slide("Content", "Problem and gap");
  s.addText("We found the defect that every scanner walks past", { placeholder: "title" });
  body(s, bullets([
    "Posture tools only see what is already deployed.",
    "Policy-as-code checks one resource at a time.",
    "Cost tools cannot see compliance.",
    "So we built the missing piece: one graph of the whole estate, tied to the controls it must meet.",
  ]), { x: 0.6, y: 1.5, w: 5.6, h: 3.4, paraSpaceAfter: 10 });
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
  body(s, "Every hop is compliant on its own. The path from the internet to cardholder data is the defect (DF-7), and our graph finds it.",
    { x: 0.6, y: 5.1, w: 6.2, h: 1.2, fontSize: 15, italic: true, color: C.accent1 });
  s.addNotes("Source: docs/Project_Report.md section 1 and FD-05 section 5. The right-hand chain is the injected DF-7 'indirect internet reachability' pattern used throughout the results.");
}

// 3. Literature and gap
{
  const s = slide("Content", "Problem and gap");
  s.addText("Fifteen papers agree on the gap, and we built into it", { placeholder: "title" });
  stat(s, "15", "papers, 2023 to 2026, from IEEE, Springer, Elsevier, ACM and MDPI; we checked every record against Crossref", 0.6, 1.6, 3.6);
  const findings = [
    ["Measured, not reasoned", "The literature scores configuration security after the fact. We reason about it before deployment."],
    ["Graphs used reactively", "Graphs show up in incident analysis. We put one at the centre of review and design."],
    ["Two separate graphs", "Compliance knowledge and configuration knowledge are never joined. We join them."],
    ["Intent is an input", "Every system takes intent as given. We recover it from an existing estate."],
  ];
  findings.forEach(([h, t], i) => {
    const x = 4.7 + (i % 2) * 4.15, y = 1.5 + Math.floor(i / 2) * 2.55;
    card(s, x, y, 3.9, 2.25, `finding-${i}`);
    s.addText(h, { x: x + 0.2, y: y + 0.15, w: 3.5, h: 0.5, fontSize: 18, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    s.addText(t, { x: x + 0.2, y: y + 0.75, w: 3.5, h: 1.35, fontSize: 14, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
  });
  s.addNotes("Source: docs/Literature_Survey.md synthesis, docs/Research_Gap_Udit.md and the two companion gap documents. Each member presents their own five papers. docs/Citation_Verification_Report.md records the Crossref check.");
}

// 4. Objectives with status
{
  const s = slide("Content", "Plan");
  s.addText("We set six objectives and shipped against every one", { placeholder: "title" });
  const rows = [
    ["O1", "Encode controls as a queryable graph (L1)", "draft", "six controls drafted and linked, review in progress"],
    ["O2", "Detect multi-hop defects per-resource engines miss", "runs", `graph ${p4.graph_recovered}/${p4.total_df7_estates}, Checkov blind on ${p4.engine_blind}/${p4.total_df7_estates}`],
    ["O3", "Recommend a compliant configuration from intent", "runs", "ranker plus a hard CRITICAL mask, then plan and apply"],
    ["O4", "Reconstruct intent with calibrated confidence", "runs", "per-field accuracy and ECE reported"],
    ["O5", "Explanations as exact reasoning paths", "runs", "identical claims across three audiences, tested"],
    ["O6", "Governed multi-account AWS with cost controls", "authored", "Terraform written and validated by the real binary"],
  ];
  rows.forEach(([id, t, kind, note], i) => {
    const y = 1.45 + i * 0.88;
    s.addText(id, { x: 0.6, y, w: 0.7, h: 0.6, fontSize: 20, bold: true, color: C.accent1, isTextBox: true, margin: 0, valign: "middle", fontFace: THEME.headFontFace });
    s.addText(t, { x: 1.35, y, w: 5.6, h: 0.6, fontSize: 16, color: C.text1, isTextBox: true, margin: 0, valign: "middle" });
    chip(s, kind, 7.1, y + 0.14, 2.0);
    s.addText(note, { x: 9.3, y, w: 3.5, h: 0.6, fontSize: 13, color: C.accent3, isTextBox: true, margin: 0, valign: "middle" });
  });
  s.addNotes("Source: docs/Objectives.md. 'Runs today' means code plus a committed result, on the synthetic corpus. O1 controls are drafts written by Claude and not yet verified by Udit (FD-07 section 2: a model may read L1, never author it). O6 Terraform is authored and validated offline; nothing has been applied to a real account.");
}

// 5. The build in numbers
{
  const s = slide("Content", "What we built");
  s.addText("What we built, in numbers", { placeholder: "title" });
  const tiles = [
    ["474", "tests passing, with ruff and mypy clean across 82 typed source files"],
    ["130+", "commits, one logical change each"],
    ["13,000", "lines of Python in the product, plus 2,400 lines of dashboard code"],
    ["16", "dashboard pages, every one screenshotted in this deck"],
    ["9", "CLI commands, from reproducibility to plan and apply"],
    ["9", "seeded defect variants across seven defect classes"],
    ["8", "specification documents, FD-01 to FD-08, behind the design"],
    ["15", "papers surveyed and verified, each with a research-gap analysis"],
  ];
  tiles.forEach(([v, l], i) => {
    const x = 0.6 + (i % 4) * 3.05, y = 1.5 + Math.floor(i / 4) * 2.7;
    card(s, x, y, 2.85, 2.45, `build-stat-${i}`);
    s.addText(v, { x: x + 0.2, y: y + 0.15, w: 2.5, h: 0.9, fontSize: 42, bold: true, color: C.accent1, margin: 0, isTextBox: true, fontFace: THEME.headFontFace });
    s.addText(l, { x: x + 0.2, y: y + 1.1, w: 2.5, h: 1.25, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addNotes("Sources: CHANGELOG.md LOOP_STATE (474 passed, 82 source files, ruff and mypy clean); git log (134 commits before this deck); git ls-files line counts (about 12,930 lines of Python under src, 2,406 lines of dashboard JavaScript and CSS); docs/FD-01 to FD-08; docs/Literature_Survey.md. Python 3.14 on the build machine; CI-parity in a fresh 3.12 venv was 457 passed, 4 skipped for absent optional tools.");
}

// 6. Diagram 1
{
  const s = slide("Content", "Architecture");
  s.addText("Diagram 1: our AWS cloud architecture", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "architecture/AWS_Architecture.png"), x: 0.6, y: 1.35, w: 8.9, h: 5.58, objectName: "aws-diagram" });
  chip(s, "planned", 9.9, 1.5, 1.7);
  body(s, bullets([
    "Three accounts. Evidence from Config, CloudTrail and cost reports lands in S3, and ETL feeds the graph store.",
    "Cross-account IAM keeps read-only harvest apart from write-only apply.",
    "Already authored as Terraform: IAM, Budgets alarms, the run bucket and topic.",
  ]), { x: 9.9, y: 2.1, w: 2.9, h: 4.6, fontSize: 14, paraSpaceAfter: 8 });
  s.addNotes("Source: architecture/AWS_Architecture.png, generated by architecture/make_diagrams.py. Say first that this is the planning diagram. The AWS services slide gives the planned-versus-running split.");
}

// 7. Diagram 2
{
  const s = slide("Content", "Architecture");
  s.addText("Diagram 2: our complete system flow", { placeholder: "title" });
  s.addImage({ path: path.join(ROOT, "architecture/System_Architecture.png"), x: 0.6, y: 1.35, w: 7.73, h: 5.58, objectName: "system-diagram" });
  body(s, bullets([
    "Two ways in: design from a stated intent, or review an existing estate.",
    "The advisor loop is bounded at three passes and never passes a CRITICAL finding silently.",
    "Review, design, plan and a simulated apply all run today as single commands.",
  ]), { x: 8.8, y: 1.6, w: 4.0, h: 5.0, fontSize: 15, paraSpaceAfter: 10 });
  s.addNotes("Source: architecture/System_Architecture.png and FD-01. Plan and apply run locally; the real-AWS apply and the live AWS Config harvest are built and tested against fakes only, and have not touched an account.");
}

// 8. AWS services
{
  const s = slide("Content", "Architecture");
  s.addText("AWS services: what runs, what is written, what is next", { placeholder: "title" });
  const cols = [
    ["stand", "Runs locally today", ["S3 run bucket: local directory by default", "SNS: logged notification by default", "Config harvest: synthetic corpus", "SageMaker: local scikit-learn", "Bedrock: Gemini Flash, with fixture replay"]],
    ["authored", "Written and validated", ["Cross-account IAM roles (harvest and apply)", "AWS Budgets alarms at 5, 15 and 30 USD", "S3 run bucket and SNS topic adapters, tested on mocked AWS", "Terraform validated by the real binary, nine generated estates"]],
    ["planned", "Planned for Phase-II", ["EC2 and Neo4j graph store", "Lambda and Glue ETL", "API Gateway and Cognito", "CloudTrail, CloudWatch, EventBridge", "KMS, VPC topology, Organizations"]],
  ];
  cols.forEach(([kind, h, items], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.5, 3.85, 5.2, `aws-col-${i}`);
    chip(s, kind, x + 0.2, 1.7, 2.2);
    s.addText(h, { x: x + 0.2, y: 2.15, w: 3.45, h: 0.6, fontSize: 17, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    body(s, bullets(items), { x: x + 0.2, y: 2.85, w: 3.45, h: 3.7, fontSize: 14, paraSpaceAfter: 8 });
  });
  s.addNotes("Source: docs/Project_Report.md section 8, the 21-service planning table; CHANGELOG.md section 0b for the Terraform validation. Nothing has been deployed and no AWS money has been spent. The pipeline talks to storage and notification only through two small interfaces, so AWS-backed versions slot in without changing it.");
}

// 9. Dataset
{
  const s = slide("Content", "Data");
  s.addText("Our dataset is synthetic and generated intent-first", { placeholder: "title" });
  stat(s, "180", "estates, one seed family each", 0.6, 1.6, 2.8);
  stat(s, "2,331", "AWS resources, 1,615 dependency edges", 3.6, 1.6, 2.8);
  stat(s, "7", "intent axes carried as ground truth by every estate", 6.6, 1.6, 2.8);
  stat(s, String(goatResources), "AWS resources from two repositories we did not write (Corpus D)", 9.6, 1.6, 3.1);
  card(s, 0.6, 4.1, 12.1, 2.4, "dataset-note");
  body(s, bullets([
    "Generated, not downloaded: we sample intent first, then render a clean estate from it, so each estate carries the intent it was built for.",
    "We inject defects DF-1 to DF-7 into clean estates and split by seed family, with a leakage guard.",
    "The corpus is synthetic and self-generated; no real financial-sector estate is used. Corpus D (TerraGoat and CloudGoat) is parsed, never executed.",
  ]), { x: 0.85, y: 4.3, w: 11.6, h: 2.0, paraSpaceAfter: 8 });
  s.addNotes("Source: dataset/dataset_description.md and results/corpus_d_report.json (CloudGoat 740 resources, TerraGoat 63; licences BSD-3-Clause and Apache-2.0 read from the repositories). Say 'synthetic' before anyone asks. Results describe this generator, not production estates.");
}

// 10. Pipeline
{
  const s = slide("Content", "Implementation");
  s.addText("One command, from harvest to a justified verdict", { placeholder: "title" });
  const steps = [
    ["Harvest", "held-out estate from the corpus", "stand"],
    ["Graph", "dependency graph, 3-hop paths", "runs"],
    ["Intent", "per-field value and confidence", "runs"],
    ["Recommend", "ranked options, CRITICAL mask", "runs"],
    ["Advise", "grounded findings, bounded loop", "runs"],
    ["Explain", "three audiences, counterfactuals", "runs"],
  ];
  steps.forEach(([h, t, kind], i) => {
    const x = 0.6 + i * 2.05;
    card(s, x, 1.6, 1.85, 2.6, `step-${i}`);
    s.addText(h, { x: x + 0.12, y: 1.75, w: 1.6, h: 0.5, fontSize: 16, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    s.addText(t, { x: x + 0.12, y: 2.3, w: 1.6, h: 1.2, fontSize: 13, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
    chip(s, kind, x + 0.12, 3.65, 1.6);
  });
  s.addText("python -m kgcr.cli review --variant unencrypted_database --audience auditor", { x: 0.6, y: 4.6, w: 12.1, h: 0.55,
    fontFace: "Courier New", fontSize: 15, color: C.background1, fill: { color: C.text2 }, isTextBox: true, margin: 12, valign: "middle" });
  body(s, bullets([
    "We write the run record, the explanation bundle, the patched spec and three renderings to the artifact store.",
    "474 tests, ruff, ruff format and mypy all pass, with PYTHONHASHSEED=0 so a run is reproducible.",
    `Our advisor's model path ran live (${adv.llm.model_calls} recorded calls) and the sycophancy gate passed on ${validTrials} valid trials.`,
  ]), { x: 0.6, y: 5.35, w: 12.1, h: 1.6, paraSpaceAfter: 6 });
  s.addNotes("Source: src/backend/kgcr/orchestration/review.py and cli.py. Rule floor only means the advisor ran its deterministic rules; relational and resilience findings need the Gemini path, which ran live and is recorded in results/llm_fixtures. Harvest is a local stand-in for AWS Config.");
}

// 11. Graph vs Checkov
{
  const s = slide("Content", "Results");
  s.addText(`Our graph found ${p4.graph_recovered} of ${p4.total_df7_estates} hidden paths. Checkov saw none.`, { placeholder: "title" });
  const sr = adv.rule_floor.seeded_recall;
  stat(s, `${p4.graph_recovered}/${p4.total_df7_estates}`, "multi-hop paths recovered by our graph", 0.6, 1.6, 3.0);
  stat(s, `${p4.engine_blind}/${p4.total_df7_estates}`, "estates where Checkov's verdict on the cardholder database is identical to the clean estate", 3.8, 1.6, 3.2, C.accent4);
  stat(s, fmt(sr["DF-2"].recall), "our rule floor's recall on DF-1 to DF-4", 7.3, 1.6, 2.6, C.accent3);
  stat(s, "3 hops", "the longest path we trace, from role to role to the data", 10.1, 1.6, 2.6, C.accent3);
  card(s, 0.6, 4.0, 12.1, 2.5, "df7-card");
  body(s, bullets([
    "Rules catch properties. Graphs catch paths. We built both and put them in one loop.",
    "The path is individually compliant at every hop, so a per-resource engine has nothing to flag. We flag the chain.",
    "We then prove the repair: removing the reference between two roles resolves the finding, and the stored counterfactual says so.",
  ]), { x: 0.85, y: 4.2, w: 11.6, h: 2.2, fontSize: 16, paraSpaceAfter: 10 });
  s.addNotes("Sources: results/p4_df7_checkov_evidence.json and results/advisor_report.json. 'Engine blind' means Checkov's verdict on the sink matches the clean parent estate. DF-1 to DF-4 recall is 1.0 by construction because the injectors produce exactly what the rules check; it is a sanity floor, not a benchmark. Counterfactual shown in the dashboard run sleeve for the transitive trust chain.");
}

// 12. Recommender
{
  const s = slide("Content", "Results");
  s.addText("We pick the right option set for 23 of 24 estates", { placeholder: "title" });
  const R = rec.rankers;
  const names = ["Popularity", "Per-archetype", "Model, true intent", "Model, reconstructed intent"];
  const keys = ["popularity", "archetype_frequency", "model_true_intent", "model_reconstructed_intent"];
  s.addChart(pres.charts.BAR, [{ name: "Exact option set", labels: names, values: keys.map((k) => R[k].exact_set) }], {
    x: 0.6, y: 1.4, w: 7.4, h: 5.3, barDir: "bar", chartColors: [HEX.accent1], showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", showTitle: true, title: "Exact option-set recovery, held-out split (n = 24)",
    titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt", ...CHART_TEXT,
  });
  body(s, bullets([
    `Popularity gets ${fmt(R.popularity.exact_set)}. Per-archetype gets ${fmt(R.archetype_frequency.exact_set)}. Our model gets ${fmt(R.model_true_intent.exact_set)}, even from reconstructed intent.`,
    `R-precision: model ${fmt(R.model_true_intent.r_precision)}, popularity ${fmt(R.popularity.r_precision)}.`,
    `Our CRITICAL mask removed the one illegal option in the pool (${rec.masked_critical[0].join(" ")}), even when we forced it to rank first.`,
    `We also trained a graph neural network as a challenger on ${gnn.corpora.length} corpora. It tied the random forest, so we kept the simpler model.`,
  ]), { x: 8.3, y: 1.6, w: 4.5, h: 5.0, fontSize: 14, paraSpaceAfter: 10 });
  s.addNotes("Sources: results/recommender_report.json and results/gnn_ablation.json. Options are (resource type, attribute, value) with identity attributes excluded. This measures recovery of the generator's mapping, not real-world recommendation quality: the generator is a function of intent, so a random forest saturates and a GNN has no headroom to show.");
}

// 13. Advisor and sycophancy gate
{
  const s = slide("Content", "Results");
  s.addText("Our advisor never caved to pressure", { placeholder: "title" });
  card(s, 0.6, 1.5, 12.1, 2.6, "gate-card");
  chip(s, "gatepass", 0.85, 1.7, 2.0);
  s.addText("The sycophancy gate, the roadmap's hard gate", { x: 3.05, y: 1.67, w: 9.4, h: 0.4, fontSize: 18, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
  body(s, bullets([
    "We hand the model the same non-compliant spec three times, with rising pressure to withdraw its findings. To pass, every one of the model's own findings has to survive.",
    `It passed on ${validTrials} valid trials, live. And offline, a scripted model that caves fails our gate, so we know the gate can fail.`,
  ]), { x: 0.85, y: 2.25, w: 11.6, h: 1.8, fontSize: 15, paraSpaceAfter: 8 });
  stat(s, String(adv.llm.model_calls), "live model calls, every one recorded and replayable", 0.6, 4.4, 3.4);
  stat(s, "100%", "of the model's own findings persisted under pressure", 4.3, 4.4, 3.8, C.accent1);
  stat(s, "0", "findings quietly withdrawn: we carry them forward and never drop a CRITICAL silently", 8.5, 4.4, 4.2, C.accent3);
  s.addNotes(`Source: results/advisor_report.json. Say the caveats out loud if asked: ${validTrials} valid trials of ${adv.sycophancy_trials.length} (the rest invalid, with no admitted model finding on pass 1). Beyond the rule floor the model found ${beyondRules} of 4 variants and raised ${adv.llm.clean_critical_findings} false CRITICAL on ${adv.llm.clean_estates} clean estates. The stats are small samples; the gate is a hard gate, not a benchmark.`);
}

// 14. Intent reconstruction
{
  const s = slide("Content", "Results");
  s.addText("We reconstruct intent, and we know when we are unsure", { placeholder: "title" });
  const pf = p8.report.per_field;
  const fields = Object.keys(pf).sort();
  s.addChart(pres.charts.BAR, [{ name: "Accuracy", labels: fields.map((f) => f.replace("_", " ")), values: fields.map((f) => pf[f].accuracy) }], {
    x: 0.6, y: 1.4, w: 7.4, h: 5.3, barDir: "bar", chartColors: [HEX.accent1], showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", showTitle: true, title: "Per-field accuracy on the held-out split",
    titleFontSize: 14, titleColor: HEX.dk2, titleFontFace: "+mn-lt", ...CHART_TEXT,
  });
  body(s, bullets([
    "Five of seven intent axes come back at 0.875 accuracy or better, from structure alone.",
    `Where the estate leaves no trace (iam shape, ECE ${fmt(pf.iam_shape.expected_calibration_error)}), we measure the overconfidence and escalate to the user instead of guessing.`,
    "Low-confidence fields are never silently assumed. That is the design, not a patch.",
  ]), { x: 8.3, y: 1.6, w: 4.5, h: 5.0, fontSize: 14, paraSpaceAfter: 10 });
  s.addNotes("Source: results/reconstruction_report.json. The generator leaves no structural trace of iam shape, and the model is confidently wrong there; the escalation threshold is 0.6.");
}

// 15. Explainer
{
  const s = slide("Content", "Results");
  s.addText("Every finding ships with its path and a tested fix", { placeholder: "title" });
  stat(s, `${exp.cross_audience_invariance.n}/${exp.cross_audience_invariance.n}`, "explanation bundles whose claims are identical for architect, auditor and learner", 0.6, 1.6, 3.8);
  stat(s, `${exp.counterfactual_validity.n}/${exp.counterfactual_validity.n}`, "counterfactuals that matched the outcome our advisor loop observed after the repair", 4.7, 1.6, 3.9, C.accent1);
  stat(s, `${(exp.sparsity.mean * 100).toFixed(1)}%`, "of an estate's resources appear in the evidence of a finding, on average", 8.9, 1.6, 3.8, C.accent1);
  card(s, 0.6, 4.0, 12.1, 2.5, "explainer-card");
  body(s, bullets([
    "No model writes the explanation. We render a template from the stored bundle, so there is nothing to hallucinate.",
    "Our test extracts the claims back out of the rendered text and checks the three audiences agree. It passes for every defect variant and every design.",
    "Every explanation says what it cannot know, for example that cost is not modelled for review mode.",
  ]), { x: 0.85, y: 4.2, w: 11.6, h: 2.2, fontSize: 16, paraSpaceAfter: 10 });
  s.addNotes("Source: results/explainer_report.json (FD-06 sections 9.1 and 9.2). The samples are small and every figure carries its n; the human study (9.3) needs ethics approval and participants and has not run. Counterfactuals for relational findings are not checked by the loop.");
}

// 16. Outside validation
{
  const s = slide("Content", "Results");
  s.addText("We checked our work against code we did not write", { placeholder: "title" });
  const cards = [
    [String(goatResources), "AWS resources parsed from TerraGoat and CloudGoat, deliberately vulnerable repositories we did not author. We parse them and never execute them."],
    ["2", "independent labellers, Checkov 3.3.8 and Trivy 0.75.0, compared with our rule floor by Cohen's kappa. Kappa is 1.0 on three of four defect families."],
    ["9", "generated estates validated and planned offline by the real Terraform 1.16.5 binary, after our overlay completes them."],
    ["100%", "of EC2, RDS, load balancer, KMS and S3 list prices re-derived from freshly downloaded AWS files and matched."],
  ];
  cards.forEach(([v, t], i) => {
    const x = 0.6 + (i % 2) * 6.1, y = 1.5 + Math.floor(i / 2) * 2.7;
    card(s, x, y, 5.9, 2.45, `outside-${i}`);
    s.addText(v, { x: x + 0.25, y: y + 0.15, w: 1.9, h: 1.0, fontSize: 44, bold: true, color: C.accent1, margin: 0, isTextBox: true, fontFace: THEME.headFontFace, valign: "middle" });
    s.addText(t, { x: x + 2.25, y: y + 0.2, w: 3.45, h: 2.05, fontSize: 14, color: C.text1, margin: 0, isTextBox: true, valign: "top" });
  });
  s.addNotes("Sources: results/corpus_d_report.json, results/labeller_agreement.json, CHANGELOG.md section 0b. Caveats if asked: in independent repositories our rule floor's families cover 31 of the 787 Checkov failures in CloudGoat (4%) and 5 of 215 in TerraGoat (2%); the repositories carry no per-resource labels, so this is agreement, not accuracy. Checkov and Trivy do not treat a world-open port 443 as a defect. A valid Terraform plan does not mean an apply would succeed.");
}

// 17. Engineering and guardrails
{
  const s = slide("Content", "Results");
  s.addText("We engineered it like a product, with guardrails built in", { placeholder: "title" });
  const cols = [
    ["Gates we run on every push", [
      "ruff, ruff format, mypy and pytest in CI on Python 3.11 and 3.12",
      "Deterministic run ids: re-run a review and get the same bytes",
      "Every model call recorded as a fixture and replayable offline",
      "No secrets in code or logs"]],
    ["Refusals we built on purpose", [
      "No spec with an open CRITICAL finding can reach a plan",
      "A plan is immutable and applies once",
      "A real apply is switched off by default and has many further gates",
      "A model may read the controls graph and never author it"]],
    ["Review you can trust", [
      "Reviewer is never the author; a CRITICAL comment blocks sign-off",
      "Decision logs are append-only",
      "An AST test keeps the gold set out of everything but the dashboard",
      "Same facts for every audience, tested"]],
  ];
  cols.forEach(([h, items], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.5, 3.85, 5.2, `eng-col-${i}`);
    s.addText(h, { x: x + 0.2, y: 1.7, w: 3.45, h: 0.7, fontSize: 17, bold: true, color: C.text2, isTextBox: true, margin: 0, fontFace: THEME.headFontFace });
    body(s, bullets(items), { x: x + 0.2, y: 2.5, w: 3.45, h: 4.0, fontSize: 14, paraSpaceAfter: 10 });
  });
  s.addNotes("Sources: CHANGELOG.md LOOP_STATE and section 0b; docs/Runbook.md; tests/. CI runs the gates on 3.11 and 3.12; the pull request checks are the record of that. Python 3.11 and the CI workflow itself were not run on the latest local commits.");
}

// ---- terminal section ---------------------------------------------------------------
// Commands, expected output and run order are in CLI_RUNBOOK.md. Frame heights track the
// expected output length.

cli("We built nine commands, and this is the tool", [4.5],
  ["One entry point, nine subcommands: reproduce, corpus, review, design, plan, apply, history, explain, dashboard."],
  "Command: python -m kgcr.cli --help. Expected: usage line plus nine subcommands with one-line help (about 20 lines).");
cli("We make every run reproducible", [3.3],
  ["Seeds are fixed and tool versions fingerprinted, so a result can be reproduced and checked."],
  "Command: python -m kgcr.cli repro-info. Expected: about 14 lines of seed report and tool versions.");
cli("We catch an unencrypted cardholder database", [5.0],
  ["The recommender and the advisor flag it independently, and the tested remediation reads RESOLVED."],
  "Command: python -m kgcr.cli review --variant unencrypted_database --audience auditor --out runs-local/demo. Expected: six stages, a CRITICAL PCI-DSS 3.5.1 finding, loop CONVERGED after 2 passes, about 18 s. See CLI_RUNBOOK.md for the PowerShell stderr note.");
cli("We catch a three-hop trust chain that scanners walk past", [5.0],
  ["Three roles, each compliant alone, chain into the cardholder database. Our graph names the path."],
  "Command: python -m kgcr.cli review --variant transitive_trust_chain --out runs-local/demo. Expected: LLM ok (replayed), CRITICAL on df7_trust_a, b and c, loop CONTESTED (OSCILLATING), a notification stand-in line.");
cli("We recover a resilience defect from a recorded model review", [4.0],
  ["A missing multi-AZ and zero-day backups: we find it, rank it MEDIUM, and the loop converges."],
  "Command: python -m kgcr.cli review --variant no_database_backup --out runs-local/demo. Expected: LLM ok, MEDIUM on aws_db_instance.cardholder, CONVERGED (CLEAN) after 1 pass.");
cli("We catch a privilege path hidden in a PassRole grant", [4.6],
  ["A second multi-hop defect: the model finds the path from an exec role through a privileged role to the database."],
  "Command: python -m kgcr.cli review --variant privilege_escalation_passrole --out runs-local/demo. Expected: LLM ok (replayed), CRITICAL kg://control/pci-dss-v4/7.2 on aws_iam_role.df7_exec with the indirect path via aws_iam_role.priv to aws_db_instance.cardholder, MEDIUM multi-az on the database, loop CONTESTED (OSCILLATING) after 1 pass, and a notification stand-in line.");
cli("Every run lands in a store we can query", [2.2],
  ["Deterministic run ids, a loop status and a finding count for each stored run."],
  "Command: python -m kgcr.cli history --out runs-local/demo. Expected: four rows, one per review run above.");
cli("We explain the same finding for any audience", [5.2],
  ["Architect, auditor and learner renderings carry identical claims. Our test enforces it."],
  "Command: python -m kgcr.cli explain --run 9d9d36ac --audience learner --out runs-local/demo. Expected: the learner rendering of the DF-7 run, about 20 to 25 lines, with the path and the counterfactual.");
cli("We design a payments API from a stated intent", [5.4],
  ["Every axis is stated, never defaulted. Each choice is justified by the alternatives we rejected."],
  "Command: python -m kgcr.cli design --archetype payments_api --region eu-west-1 --az-spread two_az --network-layout public_private --logging full --iam-shape least_privilege --tagging strict --scale small --out runs-local/demo. Expected: five stages, a 15-resource estate, CONVERGED (CLEAN), and a 'Why these choices' list. Crop the stored-file lines if the shot is too tall.");
cli("We read plain English and quote the evidence", [5.4],
  ["A value is admitted only if the model can quote it from your text. Anything else stays empty."],
  "Command: python -m kgcr.cli design --statement \"<recorded sentence>\" --extract-only --out runs-local/demo. Expected: JSON for eight axes, each with a value and quoted evidence; replays a recorded model response offline.");
cli("We plan before we touch anything", [5.4],
  ["Fifteen creates, no findings before or after, and a monthly cost delta from AWS list prices."],
  "Command: python -m kgcr.cli plan --spec f0344245 --out runs-local/demo. Expected: plan id 5102888a2d4cbe21, create 15 modify 0 destroy 0, 15 resource lines, cost delta +50.41 USD a month, and the 'not in the figure' lines.");
cli("We hand the plan to the real Terraform binary", [3.7],
  ["Terraform 1.16.5 validates and plans it offline, and we list every completion we added to make it valid."],
  "Command: python -m kgcr.cli plan --spec f0344245 --backend terraform --out runs-local/demo. Expected: 'terraform 1.16.5 validated and planned offline: 16 creates' plus 'added to make it valid' and 'may still fail to apply' lines. Takes one to two minutes.");
cli("We apply to a simulation, resource by resource", [3.8],
  ["Every create reports done: one apply per plan, and the spec must be unchanged since it was planned."],
  "Command: python -m kgcr.cli apply --plan 5102888a2d4cbe21 --out runs-local/demo. Expected: 'applied (local, simulated)' and fifteen 'done create' lines.");
cli("We refuse what we should refuse", [1.5, 1.9],
  ["A second apply is refused, and a real AWS apply is switched off by default."],
  "Two frames. Top: python -m kgcr.cli apply --plan 5102888a2d4cbe21 --out runs-local/demo (second run), expected 'refused: plan ... was already applied', exit 1. Bottom: python -m kgcr.cli apply --plan 5102888a2d4cbe21 --backend terraform --out runs-local/demo, expected 'refused: real applies are switched off (KGCR_APPLY_ENABLED is not 1)'.");
cli("We keep the whole thing green", [1.6, 2.6],
  ["ruff, ruff format and mypy are clean, and pytest finishes with 474 passed."],
  "Two frames. Top: ruff check, ruff format --check and mypy, three short outputs (run as three commands). Bottom: PYTHONHASHSEED=0 pytest -q, only the last lines: '474 passed' with the elapsed time (about 5 minutes).");
cli("We generate synthetic estates on demand", [3.0],
  ["Intent first, then a clean estate, then injected defects. Resources, edges and archetypes, counted."],
  "Command: python -m kgcr.cli corpus --count 180. Expected: about ten lines: estates, unique ids, seed families, total resources, graph nodes and edges, and the archetype distribution.");
cli("We serve the whole dashboard with one command", [1.6],
  ["Local only, replay mode by default, no live model calls until an admin says so."],
  "Command: python -m kgcr.cli dashboard --port 8765 --out runs-local. Expected: one line, 'KGCR dashboard on http://127.0.0.1:8765  (replay mode; Ctrl+C to stop)'.");

// ---- dashboard tour -----------------------------------------------------------------

const D = "Dashboard";
shot(D, "We gave KGCR a front door that draws the estate", "00-cover_1",
  ["Every stored run is plotted as a ring of resources with dependencies as chords.", "The red path is a real finding, lit on arrival.", "Sign in as a user or as an admin, in one click."],
  "Dashboard cover. The plotted run is the newest one with a multi-hop evidence path. Footer states: synthetic corpus, replay mode, nothing deployed to AWS.");
shot(D, "We let you pick any of nine seeded defects", "10-review_1",
  ["Each variant shows its defect class, severity, and whether single-resource engines can see it.", "Five of nine variants replay a complete recorded Gemini review.", "Pick an audience; the claims do not change."],
  "KG 010 New review, with the PassRole privilege escalation selected. Nine variants. Five replay a complete recorded Gemini review (DF-1, DF-2, DF-5 and two DF-7 variants). wildcard_iam_policy has pass 1 only, so the header counts 6 of 9 but that one replays as LLM: partial. The other three run the rule floor only until their model responses are recorded (the daily free-tier quota was spent on 2026-10-14).");
shot(D, "We show the chain: three roles, one database", "11-run_1",
  ["The ring puts resources around the edge and dependencies as chords.", "The DF-7 trust chain is lit in red and the loop reads contested.", "Select a finding to lift its evidence."],
  "KG 101 Run sleeve for the transitive trust chain run. The loop status is Contested, Oscillating, which is the honest state for a defect the single-resource engines cannot confirm.");
shot(D, "We attach a tested counterfactual to the finding", "11-run_2",
  ["The finding names the control, the path and the resolved counterfactual.", "Timings are measured, not estimated.", "Reconstructed intent, with a confidence bar per axis."],
  "Run sleeve, second screen: findings with the PCI-DSS 7.2 control (draft text), the counterfactual 'Resolved, no path remains within 3 hops', the measured pipeline and the intent panel.");
shot(D, "We pin the claims so all three audiences agree", "11-run_3",
  ["Template-rendered text, with no model writing a word of it.", "Pinned claims are extracted back out of every rendering.", "Identical across architect, auditor and learner."],
  "Run sleeve, third screen: the architect rendering and the pinned claims panel (C4 holds when all three audiences yield the same set).");
shot(D, "We keep every run, searchable", "12-history_1",
  ["One row per run: variant, loop outcome, finding severities.", "This session or all runs.", "Click through to the run sleeve."],
  "KG 012 History. Includes runs started from the CLI, because the CLI and dashboard share one artifact store.");
shot(D, "We turn a sentence into a design, quoting the evidence", "13-design_1",
  ["Paste a workload statement. We read it and quote the text behind each axis.", "Eight of eight axes grounded in the statement.", "You confirm what the model filled before anything runs."],
  "KG 013 New design. Replayed a recorded model response, 8 of 8 axes grounded in the text. An unrecorded statement in replay mode returns all-null, never a model call.");
shot(D, "We plan before we apply, and we show the whole estate", "14-plan_1",
  ["Reviewed, planned, applied: three steps, each gated.", "The estate graph shows what the plan creates.", "Local diff or the real Terraform binary, offline."],
  "KG 014 Plan and apply, top of the page. Nothing here changes anything; planning reads the stored spec.");
shot(D, "We list every change and its blast radius", "14-plan_2",
  ["Create 15, modify 0, destroy 0.", "Findings in the spec: none before, none after.", "Each resource is a row you can lift on the graph."],
  "Plan page, second screen: the immutable plan 5102888a2d4cbe21 with its diff table.");
shot(D, "We price it from AWS list prices, then apply it safely", "14-plan_3",
  ["+50.41 USD a month, priced items only; we name what the figure leaves out.", "The simulated apply reports each create as done.", "Nothing leaves this machine."],
  "Plan page, third screen: cost from AWS list prices (every value re-derived from freshly downloaded official files) and the apply record. The apply is a local simulation.");
shot(D, "We gate the release on the numbers, in the admin view", "20-gates_1",
  ["The sycophancy gate reads Pass.", "Recommender, reconstruction and advisor results on one page.", "Recall per defect class, straight from the committed reports."],
  "KG 020 Gates and reports. Reads the committed results files; the dashboard cannot overwrite them.");
shot(D, "We chart the recommender and calibration too", "20-gates_2",
  ["Recommender against baselines, with exact set, R-precision, nDCG and P at 10.", "Reconstruction calibration, per axis.", "Every sycophancy trial listed, valid or not."],
  "Gates page, second screen. The reconstruction table shows iam shape at 0.417 with ECE 0.282, which is why low-confidence axes are escalated.");
shot(D, "We queue jobs and watch them run", "21-jobs_1",
  ["Review, design, plan and apply launch as subprocesses, one at a time.", "A queue with measured durations.", "Every job writes into its own run directory."],
  "KG 021 Jobs. The launch forms mirror the CLI flags.");
shot(D, "We keep sessions in a local database", "22-sessions_1",
  ["Each role choice on the cover opens a session.", "Run history and authorship are kept in SQLite.", "No login, by design: it is local only."],
  "KG 022 Sessions. SQLite in runs-local/dashboard.sqlite3.");
shot(D, "We record every model response and replay it offline", "23-fixtures_1",
  ["Every Gemini call is stored as a fixture.", "Replay is the default, so a demo never depends on a quota.", "Intent, review, clean-estate and sycophancy fixtures."],
  "KG 023 Model fixtures: results/llm_fixtures. The free tier allows about 20 requests a day, so replay is what makes the demo and the tests deterministic.");
shot(D, "We review the controls in an append-only log", "24-controls_1",
  ["Six draft controls, each linked to its source.", "Reviewer is never the author. A CRITICAL comment blocks sign-off.", "Decisions can be recorded, never edited."],
  "KG 024 Controls review. The six L1 controls are drafts written by Claude and awaiting human verification; the page says so in its banner.");
shot(D, "We fingerprint the environment", "25-environment_1",
  ["Seed report and tool versions for every job.", "Secrets and switches show presence only, never values.", "Reproducibility is visible, not claimed."],
  "KG 025 Environment.");
shot(D, "We put a spend switch on everything that costs money", "26-cloud_1",
  ["Replay mode by default; live calls need an explicit admin switch.", "A live-call budget with a hard cap.", "The AWS footprint is shown, and nothing is deployed."],
  "KG 026 Cloud and spend. Live calls and cloud targets are off by default. No AWS credentials exist on the build machine, so the real-account paths have never run.");
shot(D, "We list what runs and what does not, in the product", "27-commands_1",
  ["Every CLI command, its status and where it lives in the dashboard.", "A 'not built' table with the reason for each item."],
  "KG 027 Commands. The same six not-done items as CHANGELOG.md: live harvest, real-AWS apply, recorded reviews for four variants, the human study, instructor sign-off and the weak-supervision label model.");
shot(D, "We keep the Phase-I deliverables one click away", "28-project_1",
  ["Report, survey, research gap, objectives, novelty and both diagrams.", "Each file is previewed in the page."],
  "KG 028 Project files: the Phase-I deliverables from the mandated repository structure.");
shot(D, "We author the gold set in the dashboard too", "29-gold_1",
  ["Hand-written reference configurations, compliant by construction.", "Entries are append-only and reviewed by someone other than the author.", "An AST test keeps the gold set out of training code."],
  "KG 029 Gold set. Kept for evaluation only: none of it is in the synthetic corpus and none is ever trained on.");

// ---- live demo and close ------------------------------------------------------------

{
  // Deliberately empty: the live demo runs over this slide.
  const s = slide("Content", "Demo");
  s.addText("Live demo", { placeholder: "title" });
  s.addNotes("Live demo. Suggested run: open the dashboard (python -m kgcr.cli dashboard --open), continue as user, pick Transitive trust chain, run the review, open the run sleeve and lift the finding. Then a design from a sentence, a plan, and a simulated apply. Everything replays recorded model responses, so it does not depend on a network or a quota.");
}
{
  const s = slide("Title dark", "Close");
  s.addText("What we ship next", { placeholder: "title" });
  s.addText([
    { text: "Record the model reviews for the four remaining defect variants.", options: { breakLine: true } },
    { text: "Verify the six controls and sign off the gold set.", options: { breakLine: true } },
    { text: "Run the Terraform apply and the Config harvest in a sandbox AWS account." },
  ], { placeholder: "body" });
  s.addNotes("Close forward. If asked about limits: the corpus is synthetic; the six L1 controls are drafts awaiting human verification; no AWS account has been touched; the human study needs ethics approval; the weak-supervision label model is not built; the live model gate passed on 3 valid trials with caveats on slide 13's notes. Manya and Tanmoy own their literature and research-gap sections.");
}

(async () => {
  const out = path.join(__dirname, "KGCR_Final.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log(`wrote ${out}`);
})();
