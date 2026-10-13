// Drawing for the catalog-sleeve world: the KGCR mark, the polar estate plot, and
// ridgelines. Everything is SVG drawn from data the API returns; nothing is invented.

const NS = "http://www.w3.org/2000/svg";
const INK = "var(--ink)";

export function svgEl(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

// The mark: the estate as a ring, one evidence path bent through it the way the
// plot draws a finding, its source open and its sink filled.
export function drawMark(svg) {
  svg.setAttribute("viewBox", "0 0 100 100");
  svgEl("circle", { cx: 50, cy: 50, r: 40, fill: "none", stroke: INK, "stroke-width": 2 }, svg);
  const at = (deg) => [50 + 40 * Math.cos((deg * Math.PI) / 180), 50 + 40 * Math.sin((deg * Math.PI) / 180)];
  const [a, b, c] = [at(205), at(-25), at(95)];
  svgEl("path", {
    d: `M${a} Q50,50 ${b} Q50,50 ${c}`,
    fill: "none", stroke: INK, "stroke-width": 5, "stroke-linecap": "square",
  }, svg);
  const node = ([x, y], filled) => svgEl("rect", {
    x: x - 6, y: y - 6, width: 12, height: 12,
    fill: filled ? INK : "var(--ground)", stroke: INK, "stroke-width": 2.5,
  }, svg);
  node(a, false);
  node(b, false);
  node(c, true);
  return svg;
}

const SEVERITY_VAR = {
  CRITICAL: "var(--critical)",
  HIGH: "var(--high)",
  MEDIUM: "var(--medium)",
  ADVISORY: "var(--advisory)",
};
export const severityColour = (s) => SEVERITY_VAR[s] || INK;

// Polar estate plot. Resources sit on the ring grouped by type; each dependency is
// a chord bent through the core. `highlight(addresses, severity)` lifts a path.
export function drawEstate(svg, graph, { grid = true, labels = false } = {}) {
  svg.replaceChildren();
  // Labels sit outside the ring, so a labelled plot widens its box to keep them in view.
  svg.setAttribute("viewBox", labels ? "-90 -40 580 480" : "0 0 400 400");
  const cx = 200, cy = 200, R = 158;
  if (grid) {
    for (let r = 38; r <= R + 24; r += 30) svgEl("circle", { cx, cy, r, class: "grid" }, svg);
    for (let i = 0; i < 24; i++) {
      const a = (i * Math.PI) / 12;
      svgEl("line", { x1: cx, y1: cy, x2: cx + (R + 24) * Math.cos(a), y2: cy + (R + 24) * Math.sin(a), class: "grid faint" }, svg);
    }
  }
  const nodes = graph.nodes.map((n) => n.address).sort((x, y) => x.localeCompare(y));
  // A bare resource name repeats across types (app, main, logs); a repeated one carries its type's last word.
  const counts = new Map();
  for (const n of nodes) counts.set(n.split(".")[1], (counts.get(n.split(".")[1]) || 0) + 1);
  const labelOf = (n) => {
    const [type, name] = n.split(".");
    return counts.get(name) > 1 ? `${type.split("_").pop()}.${name}` : name;
  };
  const pos = new Map();
  nodes.forEach((n, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / nodes.length;
    pos.set(n, { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a), a });
  });
  const edgeLayer = svgEl("g", { class: "edges" }, svg);
  const edges = [];
  for (const [s, t] of graph.edges) {
    if (!pos.has(s) || !pos.has(t)) continue;
    const p = pos.get(s), q = pos.get(t);
    const path = svgEl("path", { d: `M${p.x},${p.y} Q${cx},${cy} ${q.x},${q.y}`, class: "edge" }, edgeLayer);
    path.style.setProperty("--len", Math.ceil(path.getTotalLength ? path.getTotalLength() : 400));
    edges.push({ s, t, path });
  }
  const tickLayer = svgEl("g", { class: "ticks" }, svg);
  const ticks = new Map();
  const texts = new Map();
  // Approximate label boxes (12-unit mono, ~7.4 units a character); a label that would
  // overlap one already placed steps further out from the ring.
  const placed = [];
  const fits = (b) => placed.every((p) => b.x1 > p.x2 + 4 || b.x2 < p.x1 - 4 || b.y1 > p.y2 + 2 || b.y2 < p.y1 - 2);
  const box = (x, y, w, anchor) => {
    const x1 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
    return { x1, x2: x1 + w, y1: y - 10, y2: y + 3 };
  };
  for (const n of nodes) {
    const { a } = pos.get(n);
    const tick = svgEl("line", {
      x1: cx + (R - 7) * Math.cos(a), y1: cy + (R - 7) * Math.sin(a),
      x2: cx + (R + 9) * Math.cos(a), y2: cy + (R + 9) * Math.sin(a), class: "tick",
    }, tickLayer);
    const title = svgEl("title", {}, tick);
    title.textContent = n;
    ticks.set(n, tick);
    if (labels) {
      const label = labelOf(n);
      const anchor = Math.cos(a) > 0.2 ? "start" : Math.cos(a) < -0.2 ? "end" : "middle";
      let lx = 0, ly = 0, b = null;
      for (const r of [R + 16, R + 30, R + 44, R + 58]) {
        lx = cx + r * Math.cos(a);
        ly = cy + r * Math.sin(a) + 3;
        b = box(lx, ly, label.length * 7.4, anchor);
        if (fits(b)) break;
      }
      placed.push(b);
      const text = svgEl("text", { x: lx, y: ly, class: "node-label", "text-anchor": anchor }, tickLayer);
      text.textContent = label;
      texts.set(n, text);
    }
  }
  svgEl("circle", { cx, cy, r: 13, class: "core" }, svg);

  function highlight(addresses, severity) {
    svg.classList.toggle("focused", Boolean(addresses && addresses.length));
    const set = new Set(addresses || []);
    const colour = severityColour(severity);
    const order = addresses || [];
    for (const e of edges) {
      const i = order.indexOf(e.s), j = order.indexOf(e.t);
      const hot = i > -1 && j > -1 && Math.abs(i - j) === 1;
      e.path.classList.toggle("hot", hot);
      e.path.style.stroke = hot ? colour : "";
      if (hot) edgeLayer.appendChild(e.path);
    }
    for (const [n, tick] of ticks) {
      const hot = set.has(n);
      tick.classList.toggle("hot", hot);
      tick.style.stroke = hot ? colour : "";
      texts.get(n)?.classList.toggle("hot", hot);
    }
  }
  return { highlight, nodeCount: nodes.length, edgeCount: edges.length };
}

// Ridgelines: one line per intent axis, height is the count of held-out estates in
// each confidence bin (results/reconstruction_report.json). `accent` marks one axis.
export function drawRidges(svg, perField, accent) {
  svg.replaceChildren();
  const names = Object.keys(perField).sort();
  const W = 640, step = 30, H = 64 + names.length * step;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const left = 150, right = W - 16;
  const max = Math.max(1, ...names.flatMap((n) => perField[n].bins.map((b) => b.count)));
  names.forEach((name, k) => {
    const base = 30 + (k + 1) * step;
    const pts = [[left, base]];
    for (let c = 0.5; c <= 1.0001; c += 0.01) {
      const bin = perField[name].bins.find((b) => c >= b.lower - 1e-9 && c <= b.upper + 1e-9);
      const h = bin ? (bin.count / max) * (step * 1.6) : 0;
      pts.push([left + ((c - 0.5) / 0.5) * (right - left), base - h]);
    }
    pts.push([right, base]);
    svgEl("path", { d: "M" + pts.map((p) => p.join(",")).join(" L"), class: name === accent ? "ridge accent" : "ridge" }, svg);
    const label = svgEl("text", { x: left - 12, y: base + 4, "text-anchor": "end", class: "ridge-label" }, svg);
    label.textContent = name;
  });
  for (const c of [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]) {
    const x = left + ((c - 0.5) / 0.5) * (right - left);
    const t = svgEl("text", { x, y: H - 4, "text-anchor": "middle", class: "axis-label" }, svg);
    t.textContent = c.toFixed(1);
  }
}
