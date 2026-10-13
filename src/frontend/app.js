// KGCR dashboard: a hash-routed single page over the `kgcr dashboard` JSON API.
// Every figure on screen is read from the API; this file renders, it never invents.

import { drawEstate, drawMark, drawRidges, severityColour } from "./plot.js";

const app = document.getElementById("app");

// ---------- small utilities ----------

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const kg = (n) => `KG ${String(n).padStart(3, "0")}`;
const pct = (x) => `${(x * 100).toFixed(0)}%`;
const fixed = (x, d = 3) => (typeof x === "number" ? x.toFixed(d) : "n/a");
const when = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");
const seconds = (a, b) => (a ? Math.max(0, ((b ? new Date(b) : new Date()) - new Date(a)) / 1000) : 0);
const dur = (s) => (s < 60 ? `${s.toFixed(s < 10 ? 1 : 0)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`);
const titleCase = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1).toLowerCase();

const ICON = {
  arrow: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 8h11M9 4l4 4-4 4"/></svg>',
  out: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M5 11l7-7M6 4h6v6"/></svg>',
  spend: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M8 3v6M8 11.5v1.5"/></svg>',
  stop: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>',
  lock: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><rect x="3.5" y="7" width="9" height="6"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2"/></svg>',
  next: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M3 8h9M9 5l3 3-3 3"/></svg>',
  chevron: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 2l4 4-4 4"/></svg>',
  play: '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M4.5 3v10l8-5z"/></svg>',
};
const btn = (label, { kind = "", icon = "arrow", attrs = "" } = {}) =>
  `<button class="btn ${kind}" ${attrs}><span>${esc(label)}</span><span class="tab">${ICON[icon]}</span></button>`;
const state = (s, label) => `<span class="state ${esc(String(s).toLowerCase())}"><i></i>${esc(label ?? titleCase(String(s).replace(/_/g, " ")))}</span>`;
const sev = (s) => `<span class="sev ${esc(s)}" title="${esc(titleCase(s))}"></span>`;
const notice = (text, tone = "") => `<div class="notice ${tone}" role="${tone === "error" ? "alert" : "note"}"><i></i><div>${text}</div></div>`;

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(`/api/${path}`, opts);
  } catch (err) {
    console.error("dashboard API unreachable", err);
    throw new ApiError("The dashboard server is not reachable. Is `kgcr dashboard` still running?", 0);
  }
  const body = await res.json().catch((err) => {
    console.error("non-JSON response", path, err);
    return {};
  });
  if (!res.ok) {
    if (res.status === 401) clearSession();
    throw new ApiError(body.error || `Request failed (${res.status})`, res.status);
  }
  return body;
}
const post = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json", "X-KGCR": "1" }, body: JSON.stringify(body) });

function toast(message, ok = false) {
  const t = document.createElement("div");
  t.className = `toast ${ok ? "ok" : ""}`;
  t.setAttribute("role", ok ? "status" : "alert");
  t.innerHTML = `<i></i><div>${esc(message)}</div>`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

// ---------- session (per browser tab; the database keeps the history) ----------

const SESSION_KEY = "kgcr.session";
function getSession() {
  try {
    const s = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
    return s && (s.role === "user" || s.role === "admin") ? s : null;
  } catch (err) {
    console.warn("session storage unavailable", err);
    return null;
  }
}
function setSession(s) {
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(s)); } catch (err) { console.warn("cannot store session", err); }
}
function clearSession() {
  try { sessionStorage.removeItem(SESSION_KEY); } catch (err) { console.warn("cannot clear session", err); }
}

let META = null;
async function meta(force = false) {
  if (!META || force) META = await api("meta");
  return META;
}

// ---------- routing ----------

const NAV = [
  { group: "User side", items: [
    { path: "/review", no: 10, label: "New review" },
    { path: "/run", no: 11, label: "Run sleeve" },
    { path: "/history", no: 12, label: "History" },
  ] },
  { group: "Admin side", admin: true, items: [
    { path: "/admin/gates", no: 20, label: "Gates and reports" },
    { path: "/admin/jobs", no: 21, label: "Jobs" },
    { path: "/admin/sessions", no: 22, label: "Sessions" },
    { path: "/admin/fixtures", no: 23, label: "Model fixtures" },
    { path: "/admin/controls", no: 24, label: "Draft controls" },
    { path: "/admin/environment", no: 25, label: "Environment" },
    { path: "/admin/cloud", no: 26, label: "Cloud and spend" },
    { path: "/admin/commands", no: 27, label: "Commands" },
    { path: "/admin/project", no: 28, label: "Project files" },
  ] },
];

const VIEWS = {
  "/review": viewReview,
  "/run": viewRun,
  "/history": viewHistory,
  "/admin/gates": viewGates,
  "/admin/jobs": viewJobs,
  "/admin/sessions": viewSessions,
  "/admin/fixtures": viewFixtures,
  "/admin/controls": viewControls,
  "/admin/environment": viewEnvironment,
  "/admin/cloud": viewCloud,
  "/admin/commands": viewCommands,
  "/admin/project": viewProject,
};

let timers = [];
const every = (fn, ms) => timers.push(setInterval(fn, ms));
const stopTimers = () => { timers.forEach(clearInterval); timers = []; };

function go(path) { location.hash = `#${path}`; }

// Every navigation gets a handle. A view that was superseded while it awaited the API is
// stopped at its next mount/every/go (it throws STALE, which showRoute swallows), so it can
// neither paint over the newer view nor register a timer nothing will clear. Nothing waits
// for a slow view.
let routeId = 0;
const STALE = Symbol("superseded navigation");

function routeHandle(id) {
  const isLive = () => id === routeId;
  const live = () => { if (!isLive()) throw STALE; };
  return {
    isLive,
    live,
    mount: (html) => { live(); return mount(html); },
    every: (fn, ms) => { live(); every(fn, ms); },
    go: (path) => { live(); go(path); },
  };
}

async function route() {
  const id = ++routeId;
  stopTimers();
  try {
    await showRoute(routeHandle(id));
  } catch (err) {
    if (err !== STALE) throw err;
  }
}

async function showRoute(ui) {
  const path = location.hash.replace(/^#/, "") || "/";
  const session = getSession();
  if (path === "/" || !session) return renderCover(path !== "/" && !session, ui);
  const [base, arg] = path.startsWith("/run/") ? ["/run", path.slice(5)] : [path, null];
  const view = VIEWS[base];
  if (!view) return go(session.role === "admin" ? "/admin/gates" : "/review");
  if (base.startsWith("/admin") && session.role !== "admin") {
    renderShell(base);
    return mount(`<div class="view-head"><h1><span class="catno">${kg(20)}</span> Admin only</h1></div>${notice("This view belongs to the admin side. Return to the cover and continue as admin to open it.", "attention")}`);
  }
  renderShell(base);
  try {
    await view(ui, arg);
  } catch (err) {
    if (err === STALE) throw err;
    console.error("view failed", base, err);
    ui.mount(notice(esc(err.message || "Something went wrong rendering this view."), "error"));
  }
}

function renderShell(active) {
  const s = getSession();
  const live = META && META.live_enabled;
  app.innerHTML = `
  <div class="shell">
    <aside class="rail" aria-label="Catalog">
      <a class="rail-head" href="#/" aria-label="KGCR cover"><svg id="rail-mark" aria-hidden="true"></svg><b>KGCR</b></a>
      <div class="rail-session"><span>${esc(titleCase(s.role))} session</span><span class="mono faint">${kg(s.catalog_no)}</span></div>
      <nav>
        ${NAV.filter((g) => !g.admin || s.role === "admin").map((g) => `
          <h2>${g.group}</h2>
          ${g.items.map((i) => `<a href="#${i.path}" ${i.path === active ? 'aria-current="page"' : ""}><span class="mono">${kg(i.no)}</span><span>${i.label}</span></a>`).join("")}
        `).join("")}
      </nav>
      <div class="rail-foot">
        <span class="mode ${live ? "live" : ""}"><i></i>${live ? "Live calls enabled" : "Replay mode"}</span>
        <a href="#/" class="faint">Back to the cover</a>
      </div>
    </aside>
    <main class="view" id="view" tabindex="-1"><div class="skeleton" style="height:64px;width:40%"></div></main>
  </div>`;
  drawMark(document.getElementById("rail-mark"));
  app.querySelector('.rail nav a[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "center" });
}
const mount = (html) => {
  const v = document.getElementById("view");
  if (v) v.innerHTML = html;
  return v;
};
// The five-block code, ascending severity then plot ink: the scheme's signature under every number.
const CODE_STRIP = `<span class="code-strip" aria-hidden="true"><i class="ADVISORY"></i><i class="MEDIUM"></i><i class="HIGH"></i><i class="CRITICAL"></i><i class="INK"></i></span>`;
const head = (no, title, lede = "") =>
  `<header class="view-head"><h1><span class="catno-wrap"><span class="catno">${typeof no === "number" ? kg(no) : esc(no)}</span>${CODE_STRIP}</span>${esc(title)}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</header>`;

// ---------- cover ----------

async function renderCover(expired, ui) {
  stopTimers();
  const session = getSession();
  app.innerHTML = `
  <div class="cover">
    <div class="cover-left">
      <div><div class="cover-mark"><svg id="cover-mark" aria-hidden="true"></svg><div class="wordmark" aria-label="KGCR">KGCR</div></div>${CODE_STRIP}</div>
      <div>
        <h1 class="cover-title">Knowledge graph cloud configuration review</h1>
        <p>Reviews AWS estates over a knowledge graph and justifies every finding as a path from resource to regulatory control, the same facts for every audience.</p>
      </div>
      ${expired ? notice("Choose a role to start a session. Sessions and run history are kept in the local database.", "attention") : ""}
      <div class="doors">
        <button class="door primary" data-role="user"><span class="mono">${kg(10)}</span><div><b>Continue as user</b><span class="d">Review an estate and read its reasoning</span></div><span class="tab">${ICON.arrow}</span></button>
        <button class="door" data-role="admin"><span class="mono">${kg(20)}</span><div><b>Continue as admin</b><span class="d">Gates, jobs, fixtures, controls and spend</span></div><span class="tab">${ICON.arrow}</span></button>
        ${session ? `<a class="faint" href="#${session.role === "admin" ? "/admin/gates" : "/review"}" style="font-size:13px">Resume ${esc(session.role)} session ${kg(session.catalog_no)}</a>` : ""}
      </div>
    </div>
    <div class="cover-right">
      <svg class="plot drawn" id="cover-plot" role="img" aria-label="Estate graph of the latest stored run"></svg>
      <div class="cover-caption" id="cover-caption"><span class="skeleton" style="width:220px"></span></div>
    </div>
    <footer class="cover-foot">
      <span>Synthetic, self-generated corpus. No real estate is shown.</span>
      <span id="cover-mode">Replay mode: recorded model responses, no live calls.</span>
      <span>Nothing is deployed to AWS.</span>
      <span id="cover-version"></span>
    </footer>
  </div>`;
  drawMark(document.getElementById("cover-mark"));
  app.querySelectorAll(".door").forEach((d) =>
    d.addEventListener("click", async () => {
      d.disabled = true;
      try {
        const s = await post("sessions", { role: d.dataset.role });
        setSession(s);
        go(s.role === "admin" ? "/admin/gates" : "/review");
      } catch (err) {
        d.disabled = false;
        toast(err.message);
      }
    }),
  );
  try {
    const m = await meta(true);
    ui.live();
    document.getElementById("cover-version").textContent = `kgcr ${m.version}`;
    if (m.live_enabled) document.getElementById("cover-mode").textContent = "Live calls are enabled by an admin.";
    const runs = await api("runs");
    ui.live();
    // The newest plotted run that has a multi-hop evidence path, else the newest plotted run.
    // light=1 skips the three audience renderings; the eight fetches run side by side.
    const settled = await Promise.allSettled(runs.slice(0, 8).map((r) => api(`runs/${r.prefix}?light=1`)));
    ui.live();
    for (const bad of settled.filter((x) => x.status === "rejected")) console.warn("cover skipped a run", bad.reason);
    const plotted = settled.filter((x) => x.status === "fulfilled" && x.value.summary).map((x) => x.value);
    const full = plotted.find((x) => x.bundle.findings.some((f) => f.evidence_path.length)) || plotted[0];
    const shown = full && { r: { prefix: full.prefix, jobs: full.jobs }, full };
    const cap = document.getElementById("cover-caption");
    if (!shown) {
      cap.innerHTML = `<span>No estate plotted yet. Continue as user and run a review.</span>`;
      return;
    }
    const plot = drawEstate(document.getElementById("cover-plot"), shown.full.summary.graph);
    // Only a multi-hop path earns the cover's lift; a single-resource finding would dim the whole plot for one tick.
    const f = shown.full.bundle.findings.find((x) => x.evidence_path.length);
    if (f) setTimeout(() => plot.highlight(f.evidence_path, f.severity), 1200);
    const no = shown.r.jobs.length ? kg(shown.r.jobs[0].catalog_no) : `run ${shown.r.prefix}`;
    cap.innerHTML = `<span>Plotted run ${esc(no)}, estate <span class="mono">${esc(shown.full.bundle.estate_id)}</span></span><span>${plot.nodeCount} resources, ${plot.edgeCount} dependencies</span>`;
  } catch (err) {
    if (err === STALE) throw err;
    console.error("cover data failed", err);
    document.getElementById("cover-caption").innerHTML = `<span>${esc(err.message)}</span>`;
  }
}

// ---------- KG 010 new review ----------

async function viewReview(ui) {
  const s = getSession();
  const [m, variants, jobs] = await Promise.all([meta(true), api("variants"), api(`jobs?session=${s.id}`)]);
  const params = m.jobs.review.params;
  let chosen = variants.find((v) => v.replay && v.defect_class === "DF-7") || variants[0];
  let audience = m.audiences[0];
  const canLive = s.role === "admin" && m.live_enabled;
  ui.mount(`
    ${head(10, "New review", "Pick a seeded defect, run review mode on a held-out synthetic estate, and read how each finding is justified.")}
    <div class="run-form">
      <div>
        <section class="block">
          <div class="block-head"><h2>Defect variant</h2><p>${variants.filter((v) => v.replay).length} of ${variants.length} replay recorded model responses</p></div>
          <div class="roster" role="radiogroup" aria-label="Defect variant">
            ${variants.map((v) => `
              <button class="cell" role="radio" aria-checked="${v.variant === chosen.variant}" data-variant="${esc(v.variant)}">
                <span class="top"><span class="mono">${esc(v.defect_class)}</span>${sev(v.severity)}</span>
                <b>${esc(v.name)}</b>
                <span class="meta"><span class="rec">${v.replay ? "Replays the recorded model review" : "Rule floor only, no recorded model review"}</span><span>Single-resource engines: ${esc(v.detectability)}</span></span>
              </button>`).join("")}
          </div>
        </section>
        <section class="block">
          <div class="block-head"><h2>Audience</h2><p>Changes the rendering only; the claims stay identical</p></div>
          <div class="segmented" role="group" aria-label="Audience">
            ${m.audiences.map((a) => `<button aria-pressed="${a === audience}" data-audience="${a}">${titleCase(a)}</button>`).join("")}
          </div>
        </section>
        <section class="block">
          <details class="more"><summary>${ICON.chevron} Corpus size and seed</summary>
            <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:16px">
              <label class="field" style="width:160px">Corpus size<input id="f-count" inputmode="numeric" value="${params.count.default}"><small>${params.count.low} to ${params.count.high}</small></label>
              <label class="field" style="width:200px">Seed<input id="f-seed" inputmode="numeric" value="${params.seed.default}"></label>
            </div>
            <p class="faint" style="font-size:13px;margin-top:12px;max-width:70ch">Recorded model responses replay only at seed ${m.default_seed} and size ${m.default_count}, the values they were recorded at. Other values run the rule floor alone.</p>
          </details>
        </section>
      </div>
      <aside class="run-side">
        <div class="actions">
          ${btn("Run review", { kind: "primary", icon: "play", attrs: 'id="run-btn"' })}
          ${s.role === "admin" ? `<label class="check"><input type="checkbox" id="f-live" ${canLive ? "" : "disabled"}> Call Gemini live (spends budget)</label>
            ${canLive ? "" : `<span class="faint" style="font-size:13px">Live calls are off. An admin can enable them in <a href="#/admin/cloud">${kg(26)}</a>.</span>`}` : ""}
        </div>
        <figure class="seed-plot"><svg class="plot" id="seed-plot" role="img" aria-label="Held-out estate for the selected variant"></svg><figcaption id="seed-caption" class="faint"></figcaption></figure>
        <div id="selection" style="font-size:14px"></div>
        <div id="job-panel"></div>
      </aside>
    </div>`);

  const describe = () => {
    const svg = document.getElementById("seed-plot");
    if (chosen.graph) {
      const p = drawEstate(svg, chosen.graph);
      p.highlight(chosen.seeded, chosen.severity);
      document.getElementById("seed-caption").textContent = `The estate this variant is seeded into: ${p.nodeCount} resources. Lifted: ${chosen.seeded.join(", ")}.`;
    } else {
      svg.replaceChildren();
      document.getElementById("seed-caption").textContent = "No held-out estate admits this variant.";
    }
    document.getElementById("selection").innerHTML = `
      <dl class="titleblock" style="border:1px solid var(--hair)">
        <div><dt>Variant</dt><dd>${esc(chosen.name)} <span class="mono faint">${esc(chosen.variant)}</span></dd></div>
        <div><dt>Severity</dt><dd>${sev(chosen.severity)} ${esc(titleCase(chosen.severity))}</dd></div>
        <div><dt>Model review</dt><dd>${chosen.replay ? state("ok", "Recorded responses replay") : state("not_run", "Rule floor only")}</dd></div>
        <div><dt>Held-out estate</dt><dd class="mono">${esc(chosen.estate_id || "none admits this variant")}</dd></div>
      </dl>`;
  };
  describe();
  app.querySelectorAll(".cell").forEach((c) =>
    c.addEventListener("click", () => {
      chosen = variants.find((v) => v.variant === c.dataset.variant);
      app.querySelectorAll(".cell").forEach((x) => x.setAttribute("aria-checked", String(x === c)));
      describe();
    }),
  );
  app.querySelectorAll("[data-audience]").forEach((b) =>
    b.addEventListener("click", () => {
      audience = b.dataset.audience;
      app.querySelectorAll("[data-audience]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    }),
  );

  const panel = document.getElementById("job-panel");
  const runBtn = document.getElementById("run-btn");
  const active = jobs.find((j) => j.kind === "review" && (j.status === "running" || j.status === "queued"));
  if (active) watchJob(ui, active.id, panel, runBtn);

  runBtn.addEventListener("click", async () => {
    const live = document.getElementById("f-live");
    const body = {
      session: s.id,
      kind: "review",
      params: {
        variant: chosen.variant,
        audience,
        count: document.getElementById("f-count").value,
        seed: document.getElementById("f-seed").value,
        ...(live && live.checked ? { live: true } : {}),
      },
    };
    runBtn.disabled = true;
    try {
      const job = await post("jobs", body);
      if (ui.isLive()) watchJob(ui, job.id, panel, runBtn);
    } catch (err) {
      runBtn.disabled = false;
      panel.innerHTML = notice(esc(err.message), "error");
    }
  });
}

function watchJob(ui, id, panel, runBtn) {
  ui.live();
  runBtn.disabled = true;
  runBtn.classList.add("busy");
  const tick = async () => {
    let job;
    try {
      job = await api(`jobs/${id}`);
    } catch (err) {
      if (ui.isLive()) panel.innerHTML = notice(esc(err.message), "error");
      return;
    }
    if (!ui.isLive()) return; // the operator moved on while this request was in flight
    const tail = (job.log || "").split("\n").slice(-14).join("\n");
    const where = job.queue_position ? `Queued, position ${job.queue_position}` : job.status === "running" ? `Running for ${dur(seconds(job.started_at))}` : "";
    panel.innerHTML = `
      <div class="job-live">
        <div class="row"><span class="mono">${kg(job.catalog_no)}</span>${state(job.status)}</div>
        ${where ? `<span class="faint" style="font-size:13px">${esc(where)}</span>` : ""}
        <pre class="log">${esc(tail) || "Waiting for output"}</pre>
        ${job.status === "queued" || job.status === "running" ? btn("Cancel", { kind: "danger", icon: "stop", attrs: 'id="cancel-btn"' }) : ""}
      </div>`;
    const cancel = document.getElementById("cancel-btn");
    if (cancel) cancel.onclick = () => post(`jobs/${id}/cancel`, { session: getSession().id }).catch((e) => toast(e.message));
    if (["done", "failed", "cancelled"].includes(job.status)) {
      stopTimers();
      runBtn.disabled = false;
      runBtn.classList.remove("busy");
      if (job.status === "done" && job.run_prefix) ui.go(`/run/${job.run_prefix}`);
      else if (job.status === "failed") panel.insertAdjacentHTML("afterbegin", notice(`The review failed with exit code ${esc(job.exit_code)}. The log below shows where.`, "error"));
    }
  };
  tick();
  ui.every(tick, 1000);
}

// ---------- KG 011 run sleeve ----------

async function viewRun(ui, prefix) {
  if (!prefix) {
    const runs = await api("runs");
    if (!runs.length) {
      return ui.mount(`${head(11, "Run sleeve")}<div class="empty"><p>No review has been stored yet. Runs appear here once a review finishes.</p>${btn("Start a review", { kind: "primary", attrs: 'data-go="/review"' })}</div>`);
    }
    return ui.go(`/run/${runs[0].prefix}`);
  }
  const [run, m] = await Promise.all([api(`runs/${prefix}`), meta()]);
  const job = (run.jobs || [])[0];
  const b = run.bundle, sum = run.summary;
  const variantName = sum ? (await api("variants")).find((v) => v.variant === sum.variant)?.name || sum.variant : "Variant not recorded";
  const llm = sum ? sum.llm_mode : (run.record.model_version.includes("gemini") ? "ok" : "disabled");
  const llmLabel = { ok: "Model reviewed every pass", partial: "Model on some passes, rule floor on others", disabled: "Rule floor only", missing_fixture: "Rule floor only, no recorded response" }[llm] || llm;

  ui.mount(`
    ${head(job ? job.catalog_no : `Run ${run.prefix}`, variantName, `Estate <span class="mono">${esc(b.estate_id)}</span> from the held-out synthetic split. Run ${esc(run.prefix)}.`)}
    ${b.scope_note ? notice(esc(b.scope_note), "attention") : ""}
    <section class="block" style="margin-top:${b.scope_note ? "24px" : "0"}">
      <div class="sleeve">
        <div class="sleeve-plot">
          ${sum ? `<svg class="plot drawn" id="run-plot" role="img" aria-label="Estate graph with ${sum.graph.nodes.length} resources"></svg>
            <p class="faint" style="font-size:13px">Resources on the ring, dependencies as chords. Select a finding to lift its evidence.</p>`
            : `<div class="empty"><p>No estate graph was recorded for this run; it predates <span class="mono">summary.json</span>. Run the same variant again to plot it.</p></div>`}
        </div>
        <dl class="titleblock">
          <div><dt>Loop</dt><dd>${state(b.loop_status)} <span class="faint">${esc(titleCase(b.loop_reason))}</span></dd></div>
          <div><dt>Advisor</dt><dd>${state(llm === "ok" ? "ok" : llm === "partial" ? "partial" : "not_run", llmLabel)}</dd></div>
          <div><dt>Findings</dt><dd>${b.findings.length ? `<span class="strip">${b.findings.map((f) => sev(f.severity)).join("")}</span> ${esc(countBySeverity(b.findings))}` : '<span class="faint">None</span>'}</dd></div>
          ${sum ? `<div><dt>Defect class</dt><dd>${esc(sum.defect_class)}, single-resource engines: ${esc(sum.detectability)}</dd></div>` : ""}
          <div><dt>Seed</dt><dd class="mono">${esc(run.record.seed)}</dd></div>
          <div><dt>Model version</dt><dd class="mono">${esc(run.record.model_version)}</dd></div>
          <div><dt>Graph version</dt><dd class="mono">${esc(run.record.graph_version)}</dd></div>
          <div><dt>Run id</dt><dd class="mono">${esc(run.record.run_id.slice(0, 32))}</dd></div>
          <div><dt>Recorded</dt><dd>${esc(when(run.record.created_at))}</dd></div>
        </dl>
      </div>
    </section>

    <section class="block">
      <div class="block-head"><h2>Findings</h2><p>${esc(b.cost_note)}</p></div>
      ${b.findings.length ? `<div class="findings">${b.findings.map((f, i) => `
        <button class="finding" data-i="${i}" aria-pressed="false">
          ${sev(f.severity)}
          <div>
            <h3>${esc(f.assertion)}</h3>
            <div class="path mono">${(f.evidence_path.length ? f.evidence_path : f.affected_elements).map(esc).join(ICON.next)}</div>
          </div>
          <aside>
            <span><span class="k">Control</span><br><span class="mono">${esc(f.control_ref)}</span>${f.control_verified ? "" : ' <span class="faint">(draft)</span>'}</span>
            <span><span class="k">Counterfactual</span><br>${f.counterfactual ? `${state(f.counterfactual.outcome === "RESOLVED" ? "pass" : "fail", titleCase(f.counterfactual.outcome))} <span class="faint">${esc(f.counterfactual.detail)}</span>` : '<span class="faint">None evaluated</span>'}</span>
          </aside>
        </button>`).join("")}</div>` : `<div class="empty"><p>The advisor raised no findings on this estate.</p></div>`}
    </section>

    ${sum ? pipelineBlock(sum, run.timings) : ""}

    <section class="block">
      <div class="block-head"><h2>Explanation</h2><p>Template rendering of the bundle; no model writes this text</p></div>
      <div class="segmented" role="group" aria-label="Audience">${m.audiences.map((a, i) => `<button data-a="${a}" aria-pressed="${i === 0}">${titleCase(a)}</button>`).join("")}</div>
      <div class="explain">
        <pre class="rendering" id="rendering"></pre>
        <div>
          <div class="block-head"><h2 style="font-size:14px">Pinned claims</h2></div>
          <div id="claims-check" style="margin-bottom:12px"></div>
          <div class="claims" id="claims"></div>
          <p class="faint" style="font-size:13px;margin-top:14px">Controls, severities, resources and outcomes extracted back out of each rendering. Claim C4 holds when all three audiences yield the same set.</p>
        </div>
      </div>
    </section>`);

  let plot = null;
  if (sum) {
    const svg = document.getElementById("run-plot");
    // Narrow screens drop ring labels and keep the full ring; the findings list names the path.
    plot = drawEstate(svg, sum.graph, { labels: svg.parentElement.clientWidth >= 480 });
  }
  const buttons = [...app.querySelectorAll(".finding")];
  buttons.forEach((el) =>
    el.addEventListener("click", () => {
      const on = el.getAttribute("aria-pressed") !== "true";
      buttons.forEach((x) => x.setAttribute("aria-pressed", "false"));
      el.setAttribute("aria-pressed", String(on));
      const f = b.findings[Number(el.dataset.i)];
      if (plot) plot.highlight(on ? (f.evidence_path.length ? f.evidence_path : f.affected_elements) : null, f.severity);
    }),
  );
  if (plot && b.findings.length) setTimeout(() => buttons[0] && buttons[0].click(), 1100);

  const sets = Object.values(run.claims).map((c) => c.join("\u0000"));
  const same = sets.every((x) => x === sets[0]);
  document.getElementById("claims-check").innerHTML = same
    ? state("pass", `Identical across ${sets.length} audiences`)
    : state("fail", "Claim sets differ between audiences");
  const showAudience = (a) => {
    const claims = run.claims[a];
    let text = esc(run.explanations[a]);
    for (const c of [...claims].sort((x, y) => y.length - x.length)) {
      text = text.split(esc(c)).join(`\u0001${esc(c)}\u0002`);
    }
    document.getElementById("rendering").innerHTML = text.replace(/\u0001/g, "<mark>").replace(/\u0002/g, "</mark>");
    document.getElementById("claims").innerHTML = claims.map((c) => `<code>${esc(c)}</code>`).join("");
  };
  showAudience(m.audiences[0]);
  app.querySelectorAll("[data-a]").forEach((x) =>
    x.addEventListener("click", () => {
      app.querySelectorAll("[data-a]").forEach((y) => y.setAttribute("aria-pressed", String(y === x)));
      showAudience(x.dataset.a);
    }),
  );
}

function countBySeverity(findings) {
  const n = {};
  for (const f of findings) n[f.severity] = (n[f.severity] || 0) + 1;
  return ["CRITICAL", "HIGH", "MEDIUM", "ADVISORY"].filter((s) => n[s]).map((s) => `${n[s]} ${s.toLowerCase()}`).join(", ");
}

function pipelineBlock(sum, timings) {
  const total = (timings || []).reduce((a, t) => a + t.seconds, 0);
  const longest = Math.max(0, ...(timings || []).map((t) => t.seconds));
  const fields = Object.entries(sum.intent.fields).sort(([a], [b]) => a.localeCompare(b));
  const chosen = sum.recommended.filter((r) => r.score >= 0.5).length;
  return `
    <section class="block">
      <div class="block-head"><h2>Pipeline</h2><p>${timings ? `Measured wall-clock, ${dur(total)} in total; widths to scale` : "No timings recorded"}</p></div>
      ${timings ? `<div class="timeline" role="img" aria-label="Stage durations">${timings.map((t) => `<div style="flex:${Math.max(t.seconds, total * 0.012)}" class="${t.seconds === longest ? "long" : ""}" title="${esc(t.stage)}: ${t.seconds.toFixed(2)} s">${t.seconds >= total * 0.12 ? `${esc(titleCase(t.stage))} ${t.seconds.toFixed(1)} s` : ""}</div>`).join("")}</div>
        <p class="mono faint" style="font-size:11.5px;margin:8px 0 0">${timings.map((t) => `${esc(t.stage)} ${t.seconds.toFixed(2)} s`).join(", ")}</p>` : ""}
      <div class="stages">
        <div class="stage"><h3>Graph</h3><div class="kv"><span>Resources</span><span class="num">${sum.graph.nodes.length}</span><span>Dependencies</span><span class="num">${sum.graph.edges.length}</span><span>Region</span><span class="mono">${esc(sum.intent.region)}</span></div></div>
        <div class="stage"><h3>Reconstructed intent</h3><div class="kv">${fields.map(([name, f]) => `<span>${esc(name)} <span class="mono faint">${esc(f.value)}</span></span><span class="bar ${f.confidence < sum.escalation_threshold ? "hi" : ""}" title="confidence ${f.confidence.toFixed(2)}"><b style="width:${pct(f.confidence)}"></b></span>`).join("")}</div>
          <span class="faint" style="font-size:12.5px">${sum.escalated.length ? `Below ${sum.escalation_threshold}, confirm with the user: ${esc(sum.escalated.join(", "))}` : `Every axis above the ${sum.escalation_threshold} escalation threshold`}</span></div>
        <div class="stage"><h3>Recommendation</h3><div class="kv"><span>Recommended (score 0.5 or more)</span><span class="num">${chosen}</span><span>Ranked after the critical mask</span><span class="num">${sum.recommended.length}</span><span>Recommended, not in estate</span><span class="num">${sum.missing_from_estate.length}</span><span>In estate, not recommended</span><span class="num">${sum.unexpected_in_estate.length}</span></div>
          ${sum.missing_from_estate.length ? `<span class="mono faint" style="font-size:11.5px">${sum.missing_from_estate.map((o) => esc(o.join(" "))).join("<br>")}</span>` : ""}</div>
        <div class="stage"><h3>Advisor loop</h3><div class="kv">${sum.loop.passes.map((p, i) => `<span>Pass ${i + 1} <span class="faint">${esc(p.llm_status.replace(/_/g, " "))}</span></span><span class="strip">${p.findings.map((f) => sev(f.severity)).join("") || '<span class="faint">clean</span>'}</span>`).join("")}</div>
          <span class="faint" style="font-size:12.5px">${esc(titleCase(sum.loop.status))} after ${sum.loop.passes.length} pass${sum.loop.passes.length === 1 ? "" : "es"}, ${esc(sum.loop.reason.toLowerCase())}</span></div>
      </div>
    </section>`;
}

// ---------- KG 012 history ----------

async function viewHistory(ui) {
  const s = getSession();
  const [runs, mine] = await Promise.all([api("runs"), api(`jobs?session=${s.id}`)]);
  const minePrefixes = new Set(mine.filter((j) => j.run_prefix).map((j) => j.run_prefix));
  let scope = minePrefixes.size ? "mine" : "all";
  const render = () => {
    const rows = scope === "mine" ? runs.filter((r) => minePrefixes.has(r.prefix)) : runs;
    document.getElementById("history").innerHTML = rows.length ? `
      <div class="table-wrap"><table>
        <thead><tr><th>Entry</th><th>Recorded</th><th>Variant</th><th>Loop</th><th>Findings</th><th>Advisor</th><th>Run</th></tr></thead>
        <tbody>${rows.map((r) => `
          <tr class="link" tabindex="0" data-prefix="${esc(r.prefix)}">
            <td class="mono">${r.jobs.length ? kg(r.jobs[0].catalog_no) : '<span class="faint">CLI</span>'}</td>
            <td>${esc(when(r.created_at))}</td>
            <td>${esc(r.variant || "not recorded")}</td>
            <td>${state(r.loop_status)}</td>
            <td><span class="strip">${r.severities.map(sev).join("") || '<span class="faint">none</span>'}</span></td>
            <td>${esc(r.llm_mode || (r.model_version.includes("gemini") ? "ok" : "rule floor"))}</td>
            <td class="mono faint">${esc(r.prefix)}</td>
          </tr>`).join("")}</tbody></table></div>`
      : `<div class="empty"><p>${scope === "mine" ? "This session has not stored a run yet." : "No runs are stored yet."}</p>${btn("Start a review", { kind: "primary", attrs: 'data-go="/review"' })}</div>`;
    app.querySelectorAll("tr.link").forEach((tr) => {
      const open = () => go(`/run/${tr.dataset.prefix}`);
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => e.key === "Enter" && open());
    });
  };
  ui.mount(`
    ${head(12, "History", "Every review stored in the local artifact store, including runs made from the CLI.")}
    <div class="segmented" role="group" aria-label="Scope" style="margin-bottom:20px">
      <button data-scope="mine" aria-pressed="${scope === "mine"}">This session</button>
      <button data-scope="all" aria-pressed="${scope === "all"}">All runs (${runs.length})</button>
    </div>
    <div id="history"></div>`);
  app.querySelectorAll("[data-scope]").forEach((x) =>
    x.addEventListener("click", () => {
      scope = x.dataset.scope;
      app.querySelectorAll("[data-scope]").forEach((y) => y.setAttribute("aria-pressed", String(y === x)));
      render();
    }),
  );
  render();
}

// ---------- KG 020 gates and reports ----------

async function viewGates(ui) {
  const { advisor: adv, recommender: rec, reconstruction: recon } = await api("reports");
  const llm = adv && typeof adv.llm === "object" ? adv.llm : null;
  const trials = (adv && adv.sycophancy_trials) || [];
  const valid = trials.filter((t) => t.valid).length;
  const fields = recon ? recon.report.per_field : {};
  const weakest = Object.entries(fields).sort(([, a], [, b]) => a.accuracy - b.accuracy)[0]?.[0];
  const rankers = rec ? rec.rankers : {};
  const bestBaseline = Object.entries(rankers).filter(([k]) => !k.startsWith("model")).sort(([, a], [, b]) => b.exact_set - a.exact_set)[0];
  const gate = adv ? adv.sycophancy_gate : "NOT_RUN";
  ui.mount(`
    ${head(20, "Gates and reports", "Read from results/*.json, the committed evidence. Jobs write their own copies and never overwrite these.")}
    <div class="gate-list">
      <div class="gate-line lead"><span class="mono faint">advisor</span><span>Sycophancy gate</span><span class="v ${gate === "PASS" ? "" : "fail"}">${esc(titleCase(gate.replace("_", " ")))}</span><p>${valid} valid of ${trials.length} trials. The advisor must keep every valid finding under pushback.</p></div>
      <div class="gate-line"><span class="mono faint">advisor</span><span>LLM advisor, live run</span><span class="m">${llm ? `${llm.model_calls} calls` : "Not run"}</span><p>${llm ? `Grounding rate ${fixed(llm.grounding_rate, 2)}; ${llm.clean_critical_findings} critical finding on ${llm.clean_estates} clean estates.` : "No live model call recorded."}</p></div>
      <div class="gate-line"><span class="mono faint">reconstruction</span><span>Intent reconstruction</span><span class="m">${recon ? fixed(recon.report.overall_accuracy) : "Not run"}</span><p>Held-out accuracy over ${recon ? recon.report.n_estates : 0} estates; weakest axis ${esc(weakest || "n/a")}.</p></div>
      <div class="gate-line"><span class="mono faint">recommender</span><span>Recommender, exact set</span><span class="m">${rec ? fixed(rankers.model_reconstructed_intent.exact_set, 2) : "Not run"}</span><p>${bestBaseline ? `Against ${fixed(bestBaseline[1].exact_set, 2)} for the best baseline, ${esc(bestBaseline[0].replace(/_/g, " "))}.` : ""}</p></div>
    </div>

    <div class="two" style="margin-top:48px">
      <section>
        <div class="block-head"><h2>Seeded-defect recall, rule floor</h2><p>${adv ? `${adv.rule_floor.clean_critical_findings} criticals on ${adv.rule_floor.clean_estates} clean estates` : ""}</p></div>
        ${adv ? `<div class="table-wrap"><table><thead><tr><th>Class</th><th>Recall</th><th class="num">Value</th><th class="num">n</th></tr></thead><tbody>
          ${Object.entries(adv.rule_floor.seeded_recall).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td><div class="bar"><b style="width:${pct(v.recall)}"></b></div></td><td class="num">${fixed(v.recall, 2)}</td><td class="num">${v.n}</td></tr>`).join("")}
        </tbody></table></div><p class="faint" style="font-size:13px;margin-top:12px">${esc(adv.rule_floor.note || "")}</p>` : notice("No advisor report.", "attention")}
      </section>
      <section>
        <div class="block-head"><h2>Beyond the rule floor, with the model</h2><p>One live run, per variant</p></div>
        ${llm ? `<div class="table-wrap"><table><thead><tr><th>Variant</th><th>Found</th></tr></thead><tbody>
          ${Object.entries(llm.seeded_recall_beyond_rule_floor).map(([k, v]) => `<tr><td>${esc(k.replace(/_/g, " "))}</td><td>${v === true ? state("pass", "Found") : v === false ? state("fail", "Missed") : esc(v)}</td></tr>`).join("")}
        </tbody></table></div>` : notice("The model has not been run live, so no result is claimed.", "attention")}
        <div class="block-head" style="margin-top:32px"><h2>Sycophancy trials</h2></div>
        <div class="table-wrap"><table><thead><tr><th>Variant</th><th>Valid</th><th class="num">Raw persistence</th><th class="num">System persistence</th></tr></thead><tbody>
          ${trials.map((t) => `<tr><td>${esc(String(t.variant).replace(/_/g, " "))}</td><td>${t.valid ? state("pass", "Valid") : state("not_run", "Invalid")}</td><td class="num">${fixed(t.raw_persistence, 2)}</td><td class="num">${fixed(t.system_persistence, 2)}</td></tr>`).join("") || '<tr><td colspan="4" class="faint">No trials recorded.</td></tr>'}
        </tbody></table></div>
      </section>
    </div>

    <section class="block">
      <div class="block-head"><h2>Reconstruction calibration</h2><p>One line per intent axis; height is held-out estates per confidence bin, 0.5 to 1.0</p></div>
      <div class="two">
        <svg class="plot" id="ridges" role="img" aria-label="Confidence bin counts per intent axis"></svg>
        <div class="table-wrap"><table><thead><tr><th>Axis</th><th class="num">Accuracy</th><th class="num">ECE</th><th class="num">Mean confidence</th><th class="num">n</th></tr></thead><tbody>
          ${Object.entries(fields).sort(([a], [b]) => a.localeCompare(b)).map(([k, f]) => `<tr><td>${k === weakest ? state("partial", k) : esc(k)}</td><td class="num">${fixed(f.accuracy)}</td><td class="num">${fixed(f.expected_calibration_error)}</td><td class="num">${fixed(f.mean_confidence)}</td><td class="num">${f.n}</td></tr>`).join("")}
        </tbody></table>
        <p class="faint" style="font-size:13px;margin-top:12px">Escalation threshold ${esc(recon ? recon.escalation_threshold : "")}: below it the reconstructor asks rather than guesses.</p></div>
      </div>
    </section>

    <section class="block">
      <div class="block-head"><h2>Recommender against baselines</h2><p>${rec ? `${rec.n_test} held-out estates, ${rec.n_candidates} candidate options, ${rec.masked_critical.length} critical option hard-masked` : ""}</p></div>
      ${rec ? `<div class="table-wrap"><table><thead><tr><th>Ranker</th><th>Exact set</th><th class="num"></th><th class="num">R-precision</th><th class="num">nDCG</th><th class="num">P@10</th></tr></thead><tbody>
        ${Object.entries(rankers).map(([k, v]) => `<tr><td>${esc(k.replace(/_/g, " "))}</td><td><div class="bar"><b style="width:${pct(v.exact_set)}"></b></div></td><td class="num">${fixed(v.exact_set, 2)}</td><td class="num">${fixed(v.r_precision, 2)}</td><td class="num">${fixed(v.ndcg, 2)}</td><td class="num">${fixed(v.p_at_10, 2)}</td></tr>`).join("")}
      </tbody></table></div>` : notice("No recommender report.", "attention")}
    </section>`);
  if (recon) drawRidges(document.getElementById("ridges"), fields, weakest);
}

// ---------- KG 021 jobs ----------

async function viewJobs(ui) {
  const s = getSession();
  const m = await meta(true);
  const kinds = Object.entries(m.jobs);
  let selected = null;
  ui.mount(`
    ${head(21, "Jobs", "Every job runs as a subprocess, one at a time, and writes into its own directory under runs-local/jobs.")}
    <div class="jobs-grid">
      <section>
        <div class="block-head"><h2>Launch</h2><p>${m.live_enabled ? state("live", "Live calls enabled") : "Replay mode"}</p></div>
        <div class="launcher">
          ${kinds.map(([k, j]) => `
            <form class="launch" data-kind="${esc(k)}" novalidate>
              <header><b>${esc(j.label)}</b><span class="mono faint" style="font-size:11.5px">${esc(j.writes)}</span></header>
              <p>${esc(j.summary)}</p>
              <div class="params">
                ${Object.entries(j.params).filter(([, p]) => p.kind === "int" || p.kind === "choice").map(([n, p]) => p.kind === "choice"
                  ? `<label class="field wide">${esc(p.label)}<select name="${esc(n)}">${p.choices.map((c) => `<option ${c === p.default ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>`
                  : `<label class="field">${esc(p.label)}<input name="${esc(n)}" inputmode="numeric" value="${esc(p.default)}"></label>`).join("")}
                ${j.can_go_live ? `<label class="check" style="height:44px"><input type="checkbox" name="live" ${m.live_enabled ? "" : "disabled"}> Live</label>` : ""}
                ${btn("Run", { kind: "plain primary", icon: "play", attrs: 'type="submit"' })}
              </div>
            </form>`).join("")}
        </div>
      </section>
      <section>
        <div class="block-head"><h2>Queue and history</h2><p id="queue-note"></p></div>
        <div id="queue"><div class="skeleton" style="height:200px"></div></div>
        <div id="job-detail" style="margin-top:28px"></div>
      </section>
    </div>`);

  app.querySelectorAll("form.launch").forEach((form) =>
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const params = {};
      for (const el of form.querySelectorAll("input, select")) {
        if (el.name === "live") { if (el.checked) params.live = true; } else params[el.name] = el.value;
      }
      const submit = form.querySelector("button");
      submit.disabled = true;
      try {
        const job = await post("jobs", { session: s.id, kind: form.dataset.kind, params });
        if (!ui.isLive()) return;
        selected = job.id;
        toast(`${kg(job.catalog_no)} queued`, true);
        await refresh();
      } catch (err) {
        toast(err.message);
      } finally {
        submit.disabled = false;
      }
    }),
  );

  async function refresh() {
    let jobs;
    try {
      jobs = await api("jobs");
    } catch (err) {
      if (ui.isLive()) document.getElementById("queue").innerHTML = notice(esc(err.message), "error");
      return;
    }
    if (!ui.isLive()) return;
    const durations = jobs.map((j) => seconds(j.started_at, j.finished_at));
    const longest = Math.max(1, ...durations);
    const activeCount = jobs.filter((j) => j.status === "running" || j.status === "queued").length;
    document.getElementById("queue-note").textContent = activeCount ? `${activeCount} active` : "Idle";
    document.getElementById("queue").innerHTML = jobs.length ? `
      ${durationPlot(jobs, durations, longest, selected)}
      <div class="table-wrap"><table>
        <thead><tr><th>Entry</th><th>Job</th><th>State</th><th>Duration, to scale</th><th class="num"></th></tr></thead>
        <tbody>${jobs.map((j, i) => `
          <tr class="link" tabindex="0" data-id="${j.id}" aria-selected="${j.id === selected}">
            <td class="mono">${kg(j.catalog_no)}</td>
            <td>${esc(m.jobs[j.kind]?.label || j.kind)}${j.live ? ` ${state("live", "live")}` : ""}</td>
            <td>${state(j.status, j.queue_position ? `Queued, ${j.queue_position}` : undefined)}</td>
            <td><div class="bar"><b style="width:${pct(durations[i] / longest)}"></b></div></td>
            <td class="num mono" style="font-size:12px">${j.started_at ? dur(durations[i]) : ""}</td>
          </tr>`).join("")}</tbody></table></div>`
      : `<div class="empty"><p>No jobs yet. Launch one from the list.</p></div>`;
    app.querySelectorAll("#queue tr.link").forEach((tr) => {
      const open = () => { selected = Number(tr.dataset.id); detail(); refresh(); };
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => e.key === "Enter" && open());
    });
    if (selected) detail();
  }

  async function detail() {
    const box = document.getElementById("job-detail");
    let j;
    try { j = await api(`jobs/${selected}`); } catch (err) { if (ui.isLive()) box.innerHTML = notice(esc(err.message), "error"); return; }
    if (!ui.isLive()) return;
    const outputs = Object.entries(j.outputs || {});
    box.innerHTML = `
      <div class="block-head"><h2>${kg(j.catalog_no)} ${esc(m.jobs[j.kind]?.label || j.kind)}</h2>${state(j.status)}</div>
      <dl class="titleblock" style="border:1px solid var(--hair);margin-bottom:16px">
        <div><dt>Parameters</dt><dd class="mono">${esc(Object.entries(j.params).filter(([, v]) => v !== null).map(([k, v]) => `${k}=${v}`).join("  "))}</dd></div>
        <div><dt>Output directory</dt><dd class="mono">${esc(j.output_dir || "not started")}</dd></div>
        ${j.live ? `<div><dt>Live model calls recorded</dt><dd class="num">${j.live_calls ?? "counting"}</dd></div>` : ""}
        ${j.run_prefix ? `<div><dt>Stored run</dt><dd><a href="#/run/${esc(j.run_prefix)}">Open run ${esc(j.run_prefix)}</a></dd></div>` : ""}
      </dl>
      ${j.status === "queued" || j.status === "running" ? btn("Cancel job", { kind: "danger", icon: "stop", attrs: 'id="job-cancel"' }) : ""}
      <pre class="log tall" style="margin-top:16px">${esc(j.log || "No output yet")}</pre>
      ${outputs.map(([name, data]) => `<details class="more" style="margin-top:16px"><summary>${ICON.chevron} ${esc(name)}</summary><pre class="json" style="margin-top:10px">${esc(JSON.stringify(data, null, 2))}</pre></details>`).join("")}`;
    const c = document.getElementById("job-cancel");
    if (c) c.onclick = () => post(`jobs/${j.id}/cancel`, { session: s.id }).then(refresh).catch((e) => toast(e.message));
  }

  await refresh();
  ui.every(async () => {
    // Poll only while something is in flight; the render that shows it finishing is the last one.
    if (document.querySelector("#queue .state.running, #queue .state.queued")) await refresh();
  }, 1500);
}

// The jobs view's plot: one hairline per job in catalog order, height to measured duration.
function durationPlot(jobs, durations, longest, selected) {
  const rows = jobs.map((j, i) => ({ j, d: durations[i] })).slice(0, 40).reverse();
  const W = 640, H = 170, top = 18, base = 140, step = Math.min(28, (W - 60) / Math.max(rows.length, 1));
  const bars = rows.map(({ j, d }, i) => {
    const x = 40 + i * step + step / 2;
    const h = j.started_at ? Math.max(2, (d / longest) * (base - top)) : 2;
    return `<line x1="${x}" x2="${x}" y1="${base}" y2="${base - h}" class="${esc(j.status)}${j.id === selected ? " sel" : ""}" stroke-width="3"><title>${kg(j.catalog_no)} ${esc(j.kind)}, ${esc(j.status)}, ${dur(d)}</title></line>`;
  }).join("");
  const first = rows[0], last = rows[rows.length - 1];
  return `<svg class="duration-plot" viewBox="0 0 ${W} ${H}" role="img" aria-label="Job durations in catalog order, longest ${dur(longest)}">
    <line x1="34" x2="${W - 10}" y1="${base}" y2="${base}" stroke="var(--hair-2)"/>
    <text x="34" y="${top - 4}">${esc(dur(longest))}</text>
    ${bars}
    <text x="40" y="${H - 8}">${kg(first.j.catalog_no)}</text>
    <text x="${W - 10}" y="${H - 8}" text-anchor="end">${kg(last.j.catalog_no)}</text>
  </svg>`;
}

// ---------- KG 022 sessions ----------

async function viewSessions(ui) {
  const [sessions, jobs] = await Promise.all([api("sessions"), api("jobs")]);
  const me = getSession();
  ui.mount(`
    ${head(22, "Sessions", "Every role choice on the cover opens a session in the local database. There is no login by design.")}
    ${sessions.length ? `<div class="table-wrap"><table>
      <thead><tr><th>Entry</th><th>Role</th><th>Started</th><th>Last seen</th><th class="num">Jobs</th><th class="num">Reviews</th></tr></thead>
      <tbody>${sessions.map((x) => `<tr class="link" tabindex="0" data-id="${esc(x.id)}">
        <td class="mono">${kg(x.catalog_no)}${x.id === me.id ? ' <span class="faint">(this tab)</span>' : ""}</td>
        <td>${esc(titleCase(x.role))}</td><td>${esc(when(x.started_at))}</td><td>${esc(when(x.last_seen))}</td>
        <td class="num">${x.jobs}</td><td class="num">${x.reviews ?? 0}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty"><p>No sessions yet.</p></div>`}
    <div id="session-jobs" style="margin-top:32px"></div>`);
  app.querySelectorAll("tr.link").forEach((tr) =>
    tr.addEventListener("click", () => {
      const own = jobs.filter((j) => j.session_id === tr.dataset.id);
      document.getElementById("session-jobs").innerHTML = `
        <div class="block-head"><h2>Jobs in this session</h2></div>
        ${own.length ? `<div class="table-wrap"><table><thead><tr><th>Entry</th><th>Job</th><th>State</th><th>Created</th><th>Run</th></tr></thead><tbody>
          ${own.map((j) => `<tr><td class="mono">${kg(j.catalog_no)}</td><td>${esc(j.kind)}</td><td>${state(j.status)}</td><td>${esc(when(j.created_at))}</td><td>${j.run_prefix ? `<a href="#/run/${esc(j.run_prefix)}">${esc(j.run_prefix)}</a>` : ""}</td></tr>`).join("")}
        </tbody></table></div>` : `<p class="faint">This session has not run a job.</p>`}`;
    }),
  );
}

// ---------- KG 023 fixtures ----------

async function viewFixtures(ui) {
  const rows = await api("fixtures");
  ui.mount(`
    ${head(23, "Model fixtures", "Recorded Gemini responses. Replay reads these instead of calling the model; a live call records a new one.")}
    <div class="two">
      <div class="table-wrap"><table>
        <thead><tr><th>Label</th><th>Kind</th><th class="num">Response</th></tr></thead>
        <tbody>${rows.map((r) => `<tr class="link" tabindex="0" data-label="${esc(r.label)}"><td class="mono" style="font-size:12px">${esc(r.label)}</td><td>${esc(r.kind)}</td><td class="num">${r.response_chars} chars</td></tr>`).join("")}</tbody>
      </table></div>
      <div id="fixture"><div class="empty"><p>Select a fixture to read the recorded response.</p></div></div>
    </div>`);
  app.querySelectorAll("tr.link").forEach((tr) => {
    const open = async () => {
      app.querySelectorAll("tr.link").forEach((x) => x.setAttribute("aria-selected", String(x === tr)));
      try {
        const f = await api(`fixtures/${tr.dataset.label}`);
        if (!ui.isLive()) return;
        let pretty = f.response;
        try { pretty = JSON.stringify(JSON.parse(f.response), null, 2); } catch { /* stored as plain text; show verbatim */ }
        document.getElementById("fixture").innerHTML = `
          <dl class="titleblock" style="border:1px solid var(--hair);margin-bottom:16px">
            <div><dt>Model</dt><dd class="mono">${esc(f.model)}</dd></div>
            <div><dt>Prompt SHA-256</dt><dd class="mono">${esc(f.prompt_sha256)}</dd></div>
          </dl><pre class="json">${esc(pretty)}</pre>`;
      } catch (err) {
        document.getElementById("fixture").innerHTML = notice(esc(err.message), "error");
      }
    };
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (e) => e.key === "Enter" && open());
  });
}

// ---------- KG 024 controls ----------

async function viewControls(ui) {
  const d = await api("controls");
  const sevOf = (c) => d.classification_to_severity[c.classification] || "ADVISORY";
  const unverified = d.controls.filter((c) => !c.verified).length;
  ui.mount(`
    ${head(24, "Draft controls", "The L1 control slice the advisor grounds every finding in.")}
    ${notice(`<b>${esc(d.status)}.</b> ${unverified} of ${d.controls.length} controls are unverified. ${esc(d.note)}`, "attention")}
    <div class="table-wrap" style="margin-top:28px"><table>
      <thead><tr><th>Control</th><th>Classification</th><th>Summary</th><th>Verified</th></tr></thead>
      <tbody>${d.controls.map((c) => `<tr>
        <td class="mono" style="white-space:nowrap">${esc(c.control_ref)}</td>
        <td style="white-space:nowrap">${sev(sevOf(c))} ${esc(c.classification)}</td>
        <td style="max-width:70ch">${esc(c.summary)}${c.checked_against ? `<br><span class="faint" style="font-size:12.5px">Checked against ${esc(c.checked_against)}</span>` : ""}</td>
        <td>${c.verified ? state("pass", "Verified") : state("not_run", "Pending review")}</td></tr>`).join("")}</tbody>
    </table></div>`);
}

// ---------- KG 025 environment ----------

async function viewEnvironment(ui) {
  const e = await api("environment");
  const yes = (b, y = "Yes", n = "No") => (b ? state("pass", y) : state("not_run", n));
  ui.mount(`
    ${head(25, "Environment", "The seed report and version fingerprint as a job's child process reports them, the same facts every run record carries.")}
    ${e.error ? notice(esc(e.error), "error") : ""}
    <div class="two">
      <section><div class="block-head"><h2>Seed report</h2></div>
        <dl class="titleblock" style="border:1px solid var(--hair)">
          ${Object.entries(e.seed_report).map(([k, v]) => `<div><dt>${esc(k.replace(/_/g, " "))}</dt><dd class="mono">${esc(v)}</dd></div>`).join("")}
        </dl>
        <div class="block-head" style="margin-top:32px"><h2>Secrets and switches</h2><p>Presence only; values are never sent to the page</p></div>
        <dl class="titleblock" style="border:1px solid var(--hair)">
          <div><dt>.env file</dt><dd>${yes(e.dotenv_present, "Present", "Absent")}</dd></div>
          <div><dt>GEMINI_API_KEY</dt><dd>${yes(e.gemini_key_present, "Set", "Not set")}</dd></div>
          <div><dt>KGCR_LLM_LIVE in the server environment</dt><dd>${e.llm_live_in_env ? state("live", "1, but dashboard jobs override it to 0 unless an admin enables live") : state("not_run", "Not 1")}</dd></div>
        </dl>
      </section>
      <section><div class="block-head"><h2>Tool versions</h2></div>
        <div class="table-wrap"><table><tbody>${Object.entries(e.tool_versions).sort().map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono num">${esc(v)}</td></tr>`).join("")}</tbody></table></div>
      </section>
    </div>`);
}

// ---------- KG 026 cloud and spend ----------

async function viewCloud(ui) {
  const s = getSession();
  const [c, m, jobs, variants] = await Promise.all([api("cloud"), meta(true), api("jobs"), api("variants")]);
  const lastLive = jobs.find((j) => j.live && j.live_calls !== null && j.live_calls !== undefined);
  const used = lastLive ? Math.min(lastLive.live_calls, m.live_call_cap) : 0;
  ui.mount(`
    ${head(26, "Cloud and spend", "Nothing here runs by default. Live model calls and real AWS targets need an explicit admin switch, reset on every server restart.")}
    <section class="block">
      <div class="block-head"><h2>Live switch</h2><p>${m.gemini_key_present ? "Gemini key present" : "No Gemini key set; live review calls would fall back to replay"}</p></div>
      <div id="live-box"></div>
    </section>
    <section class="block">
      <div class="block-head"><h2>Live-call budget</h2><p>Capped at ${m.live_call_cap} model calls per process</p></div>
      <div class="budget" role="img" aria-label="${used} of ${m.live_call_cap} live calls used by the latest live job">${Array.from({ length: m.live_call_cap }, (_, i) => `<i class="${i < used ? "used" : ""}"></i>`).join("")}</div>
      <p class="faint" style="font-size:13px;margin-top:10px">${lastLive ? `${kg(lastLive.catalog_no)} recorded ${lastLive.live_calls} new fixture${lastLive.live_calls === 1 ? "" : "s"}.` : "No live job has run from the dashboard."}</p>
    </section>
    <section class="block">
      <div class="block-head"><h2>Review against real AWS targets</h2><p>Stores artifacts in S3 and publishes contested runs to SNS</p></div>
      <form id="cloud-form" class="launch" style="border-top:1px solid var(--hair-2)" novalidate>
        <div class="params">
          <label class="field wide">Variant<select name="variant">${variants.map((v) => `<option value="${esc(v.variant)}">${esc(v.name)}</option>`).join("")}</select></label>
          <label class="field wide">S3 bucket<input name="s3_bucket" placeholder="kgcr-runs-example" autocomplete="off"></label>
          <label class="field wide" style="width:360px">SNS topic ARN<input name="sns_topic_arn" placeholder="arn:aws:sns:region:account:topic" autocomplete="off"></label>
          ${btn("Run against AWS", { kind: "spend", icon: "spend", attrs: `type="submit" ${m.live_enabled && c.boto3_installed ? "" : "disabled"}` })}
        </div>
        <p class="faint" style="font-size:13px">${!c.boto3_installed ? "The aws extra (boto3) is not installed in this environment." : m.live_enabled ? "Uses the AWS credentials in the server environment. A run stored in S3 does not appear in History." : "Enable live mode above first."}</p>
      </form>
    </section>
    <section class="block">
      <div class="block-head"><h2>AWS footprint</h2><p>${c.deployed ? "" : "Authored, not applied. Nothing is deployed."}</p></div>
      <dl class="titleblock" style="border:1px solid var(--hair);margin-bottom:20px">
        <div><dt>S3 and SNS adapters (boto3)</dt><dd>${c.boto3_installed ? state("pass", "Installed, tested against moto") : state("not_run", "Not installed")}</dd></div>
        <div><dt>terraform on PATH</dt><dd>${c.terraform_installed ? state("pass", "Installed") : state("not_run", "Not installed; the Terraform has never been validated here")}</dd></div>
      </dl>
      <div class="table-wrap"><table><thead><tr><th>File</th><th>Resource</th><th>Name</th></tr></thead><tbody>
        ${c.resources.map((r) => `<tr><td class="mono">${esc(r.file)}</td><td class="mono">${esc(r.type)}</td><td>${esc(r.name)}</td></tr>`).join("")}
      </tbody></table></div>
    </section>`);

  const box = document.getElementById("live-box");
  const renderLive = (confirming = false) => {
    const on = META.live_enabled;
    box.innerHTML = on
      ? `<div class="confirm"><span>${state("live", "Live calls and cloud targets are enabled")}</span><p class="mute">Jobs that ask for live mode now call Gemini and may write to AWS. Replay stays the default for every job that does not tick Live.</p><div>${btn("Switch back to replay", { kind: "primary", icon: "stop", attrs: 'id="live-off"' })}</div></div>`
      : confirming
        ? `<div class="confirm" role="alertdialog" aria-labelledby="live-q"><b id="live-q">Enable live calls?</b><p class="mute">Each live process may make up to ${m.live_call_cap} Gemini calls on the free tier and records every response as a new fixture in results/llm_fixtures. AWS targets write to the account in the server environment.</p><div style="display:flex;gap:12px;flex-wrap:wrap">${btn("Enable live calls", { kind: "spend", icon: "spend", attrs: 'id="live-yes"' })}${btn("Keep replay", { kind: "plain", attrs: 'id="live-no"' })}</div></div>`
        : `<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">${state("ok", "Replay mode: recorded responses, local stand-ins")}${btn("Enable live calls", { kind: "spend", icon: "spend", attrs: 'id="live-ask"' })}</div>`;
    const set = async (enabled) => {
      try {
        await post("admin/live", { session: s.id, enabled, confirm: enabled });
        await meta(true);
        viewCloudRefresh();
      } catch (err) { toast(err.message); }
    };
    document.getElementById("live-ask")?.addEventListener("click", () => renderLive(true));
    document.getElementById("live-no")?.addEventListener("click", () => renderLive(false));
    document.getElementById("live-yes")?.addEventListener("click", () => set(true));
    document.getElementById("live-off")?.addEventListener("click", () => set(false));
  };
  renderLive();

  document.getElementById("cloud-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    // With neither target the server would run an ordinary local review, not an AWS one.
    if (!f.get("s3_bucket").trim() && !f.get("sns_topic_arn").trim()) {
      return toast("Name an S3 bucket or an SNS topic ARN; with neither, nothing would go to AWS.");
    }
    try {
      const job = await post("jobs", { session: s.id, kind: "review", params: { variant: f.get("variant"), s3_bucket: f.get("s3_bucket").trim(), sns_topic_arn: f.get("sns_topic_arn").trim() } });
      toast(`${kg(job.catalog_no)} queued; follow it in ${kg(21)}`, true);
    } catch (err) { toast(err.message); }
  });
}
const viewCloudRefresh = () => route();

// ---------- KG 027 commands ----------

async function viewCommands(ui) {
  const m = await meta();
  const working = [
    ["kgcr review", "Review an estate end to end, locally", "/review", 10],
    ["kgcr history", "List stored review runs", "/history", 12],
    ["kgcr explain", "Re-render a stored run for an audience", "/run", 11],
    ["kgcr corpus", "Generate Corpus A synthetic estates", "/admin/jobs", 21],
    ["kgcr repro-info", "Seed report and version fingerprint", "/admin/environment", 25],
    ["kgcr dashboard", "Serve this dashboard", "/", 0],
  ];
  ui.mount(`
    ${head(27, "Commands", "The kgcr command surface: what runs today and what is planned, with the phase it lands in.")}
    <div class="table-wrap"><table>
      <thead><tr><th>Command</th><th>What it does</th><th>Status</th><th>In the dashboard</th></tr></thead>
      <tbody>
        ${working.map(([c, d, p, n]) => `<tr><td class="mono">${esc(c)}</td><td>${esc(d)}</td><td>${state("pass", "Working")}</td><td><a href="#${p}">${kg(n)}</a></td></tr>`).join("")}
        ${m.planned.map((p) => `<tr><td class="mono">kgcr ${esc(p.command)}</td><td>${esc(p.help)}</td><td>${state("planned", `Planned, ${p.phase}`)}</td><td>${btn(`Not built, ${p.phase}`, { icon: "lock", attrs: "disabled" })}</td></tr>`).join("")}
      </tbody>
    </table></div>`);
}

// ---------- KG 028 project ----------

async function viewProject(ui) {
  const p = await api("project");
  ui.mount(`
    ${head(28, "Project files", "The Phase-I deliverables as the README lists them, and both mandated diagrams.")}
    <div class="table-wrap"><table>
      <thead><tr><th>Deliverable</th><th>File</th></tr></thead>
      <tbody>${p.deliverables.map((d) => `<tr><td>${esc(d.title)}</td><td>${/\.(md|png|svg)$/.test(d.path) ? `<a class="mono" href="/repo/${esc(d.path)}" target="_blank" rel="noopener">${esc(d.path)}</a>` : `<span class="mono">${esc(d.path)}</span>`}</td></tr>`).join("")}</tbody>
    </table></div>
    <section class="block"><div class="block-head"><h2>Architecture diagrams</h2></div>
      <div class="diagrams">${p.diagrams.map((d) => `<figure><img src="/repo/${esc(d)}" alt="${esc(d.split("/").pop().replace(/_/g, " ").replace(".png", ""))} diagram" loading="lazy"><figcaption>${esc(d)}</figcaption></figure>`).join("")}</div>
    </section>`);
}

// ---------- boot ----------

// Buttons that only navigate carry data-go; one delegated listener serves every view.
app.addEventListener("click", (e) => {
  const target = e.target.closest("[data-go]");
  if (target) go(target.dataset.go);
});

window.addEventListener("hashchange", route);
meta().catch((err) => console.error("meta failed", err)).finally(route);
