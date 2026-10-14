// KG 024 controls review and KG 029 gold set. Human acts only: every write names a person and,
// where it signs something off, asks for confirmation. Nothing here is filled in by a model.

export function makeAuthoringViews(c) {
  const { esc, btn, state, sev, notice, head, api, post, toast, getSession, when, titleCase, app } = c;
  const pretty = (s) => String(s).replace(/_/g, " ");
  const NAME_KEY = "kgcr.reviewer";
  const rememberedName = () => { try { return localStorage.getItem(NAME_KEY) || ""; } catch { return ""; } };
  const remember = (name) => { try { localStorage.setItem(NAME_KEY, name); } catch { /* a private window: the name is simply not remembered */ } };
  const download = (path) => { location.href = `/api/${path}`; };

  // ---------- KG 024 controls review ----------

  async function viewControls(ui) {
    const s = getSession();
    const d = await api("authoring/controls");
    const sevOf = (ctl) => d.classification_to_severity[ctl.classification] || "ADVISORY";
    const decided = d.controls.filter((x) => x.latest).length;
    const verified = d.controls.filter((x) => x.latest && x.latest.decision === "verified").length;
    const stateOf = (x) => !x.latest ? state("not_run", "No decision yet")
      : x.latest.decision === "verified" ? state("pass", "Verified")
        : x.latest.decision === "rejected" ? state("fail", "Rejected") : state("planned", "Needs change");
    ui.mount(`
      ${head(24, "Controls review", "Record your decision on each draft control. The log is append-only and exports as a file you commit. It never changes the controls the advisor reads.")}
      ${notice(`<b>${esc(d.status)}.</b> ${decided} of ${d.controls.length} controls have a recorded decision, ${verified} verified. ${esc(d.note)}`, "attention")}
      <section class="block" style="margin-top:28px">
        <div class="block-head"><h2>Controls</h2><p>Draft file <span class="mono">${esc(d.draft_sha256.slice(0, 12))}</span></p></div>
        <div class="controls-list">${d.controls.map((x, i) => `
          <article class="control" data-i="${i}">
            <div class="control-head">
              <span class="mono">${esc(x.control_ref)}</span>
              <span>${sev(sevOf(x))} ${esc(x.classification)}</span>
              ${stateOf(x)}
            </div>
            <p class="control-summary">${esc(x.summary)}</p>
            ${x.checked_against ? `<p class="faint" style="font-size:12.5px">Checked against ${esc(x.checked_against)}</p>` : ""}
            ${x.latest ? `<p class="faint" style="font-size:13px">Latest by ${esc(x.latest.reviewer)}, ${esc(when(x.latest.created_at))}${x.latest.note ? `: ${esc(x.latest.note)}` : ""}${x.latest.proposed_summary ? `<br>Proposed wording: ${esc(x.latest.proposed_summary)}` : ""} <span class="mono">${x.decisions} on record</span></p>` : ""}
            ${s.role === "admin" ? `<details class="more"><summary>${c.ICON.chevron} Record a decision</summary>
              <form class="decision" data-node="${esc(x.control_node)}" novalidate>
                <div class="segmented" role="group" aria-label="Decision for ${esc(x.control_ref)}">
                  ${["verified", "needs_change", "rejected"].map((v, k) => `<button type="button" data-decision="${v}" aria-pressed="${k === 0}">${esc(titleCase(pretty(v)))}</button>`).join("")}
                </div>
                <label class="field proposed" hidden>Proposed summary<textarea name="proposed_summary" aria-label="Proposed summary" rows="3" maxlength="1000"></textarea></label>
                <label class="field">Note<textarea name="note" aria-label="Note" rows="2" maxlength="2000" placeholder="What you checked, and against what"></textarea></label>
                <label class="field" style="max-width:320px">Your name<input name="reviewer" aria-label="Your name" maxlength="80" autocomplete="name" value="${esc(rememberedName())}"></label>
                <label class="check"><input type="checkbox" name="confirm"> This is my own decision</label>
                <div>${btn("Record decision", { kind: "primary", icon: "next", attrs: 'type="submit"' })}</div>
              </form></details>` : ""}
          </article>`).join("")}</div>
      </section>
      <section class="block">
        <div class="block-head"><h2>Export</h2><p>A download, not a write into the repository</p></div>
        <p class="faint" style="font-size:13px;max-width:72ch;margin-bottom:14px">The file lists every decision with who made it and when. Save it under results/ and commit it yourself. Promoting reviewed controls into the file the advisor reads is a separate step: it makes a new graph version, and any change to a summary invalidates the recorded model responses, which would have to be re-recorded.</p>
        ${btn("Export decisions", { icon: "arrow", attrs: 'id="export-btn" type="button"' })}
      </section>`);

    document.getElementById("export-btn").addEventListener("click", () => download("authoring/controls/export"));
    app.querySelectorAll("form.decision").forEach((form) => {
      let decision = "verified";
      const proposed = form.querySelector(".proposed");
      form.querySelectorAll("[data-decision]").forEach((b) =>
        b.addEventListener("click", () => {
          decision = b.dataset.decision;
          form.querySelectorAll("[data-decision]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
          proposed.hidden = decision !== "needs_change";
        }),
      );
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = new FormData(form);
        const reviewer = String(f.get("reviewer") || "").trim();
        if (!reviewer) return toast("Enter your name: a decision is recorded against a person.");
        if (!form.querySelector("[name=confirm]").checked) return toast("Tick the box to confirm this is your own decision.");
        try {
          await post("authoring/controls/decision", {
            session: s.id, control_node: form.dataset.node, decision, reviewer,
            note: f.get("note"), proposed_summary: decision === "needs_change" ? f.get("proposed_summary") : null, confirm: true,
          });
          remember(reviewer);
          toast("Decision recorded.", true);
          c.reload();
        } catch (err) { toast(err.message); }
      });
    });
  }

  // ---------- KG 029 gold set ----------

  async function viewGold(ui) {
    const s = getSession();
    const [g, ctl] = await Promise.all([api("gold"), api("authoring/controls")]);
    const admin = s.role === "admin";
    const cells = Array.from({ length: g.target }, (_, i) => {
      const e = g.entries[i];
      return `<i class="${e ? (e.status === "reviewed" ? "reviewed" : e.status === "authored" ? "authored" : "") : ""}"></i>`;
    }).join("");
    const stateOfEntry = (e) => e.status === "reviewed" ? state("pass", "Signed off") : e.status === "authored" ? state("planned", "Authored") : state("not_run", "Draft");
    ui.mount(`
      ${head(29, "Gold set", "Hand-authored reference configurations, compliant by construction, kept for evaluation only. None is drawn from the synthetic corpus and none is ever trained on.")}
      <section class="block">
        <div class="block-head"><h2>Progress</h2><p>${g.authored} authored and ${g.reviewed} signed off, of ${g.target} to reach</p></div>
        <div class="gold-progress" role="img" aria-label="${g.authored} of ${g.target} authored, ${g.reviewed} signed off">${cells}</div>
        <p class="faint" style="font-size:13px;margin-top:10px;max-width:72ch">Each configuration comes from the Well-Architected Framework, the Security Reference Architecture or a published financial-services reference, and is checked here by the single-resource rule floor. A CRITICAL on a compliant configuration is a false positive or an error in the control encoding. The check does not cover relational findings.</p>
      </section>
      <section class="block">
        <div class="block-head"><h2>Entries</h2><p>${g.entries.length ? "Select one to read it" : "None yet"}</p></div>
        ${g.entries.length ? `<div class="table-wrap"><table>
          <thead><tr><th>No.</th><th>Title</th><th>Source</th><th>Status</th><th>Author</th><th>Signed off by</th></tr></thead>
          <tbody>${g.entries.map((e) => `<tr class="link" tabindex="0" data-id="${e.id}"><td class="mono">${e.id}</td><td>${esc(e.title)}</td><td>${esc(e.framework)}</td><td>${stateOfEntry(e)}</td><td>${esc(e.author)}</td><td>${esc(e.reviewer || "")}</td></tr>`).join("")}</tbody>
        </table></div>` : '<div class="empty"><p>No gold entry has been written yet.</p></div>'}
        <div id="entry-panel" style="margin-top:24px"></div>
      </section>
      ${admin ? `<section class="block">
        <div class="block-head"><h2 id="form-title">New entry</h2><p>Transcribed by you from the cited source</p></div>
        <form id="gold-form" novalidate>
          <div class="axes">
            <label class="field">Title<input name="title" aria-label="Title" maxlength="160"></label>
            <label class="field">Source framework<select name="framework" aria-label="Source framework">${g.frameworks.map((f) => `<option>${esc(f)}</option>`).join("")}</select></label>
          </div>
          <label class="field" style="margin-top:16px">Source reference<input name="source_ref" aria-label="Source reference" maxlength="1000" placeholder="Pillar, section and the page or URL you took it from"></label>
          <fieldset class="control-picks"><legend>Controls this configuration exercises</legend>
            ${ctl.controls.map((x) => `<label class="check"><input type="checkbox" name="controls" value="${esc(x.control_node)}"> <span class="mono">${esc(x.control_ref)}</span></label>`).join("")}
          </fieldset>
          <label class="field" style="margin-top:16px">Configuration, as Terraform JSON<textarea name="config" aria-label="Configuration as Terraform JSON" rows="12" class="mono-area" spellcheck="false"></textarea><small>A <span class="mono">resource</span> block. Checked for syntax and run through the rule floor on save.</small></label>
          <label class="field" style="margin-top:16px;max-width:320px">Your name<input name="author" aria-label="Your name" maxlength="80" autocomplete="name" value="${esc(rememberedName())}"></label>
          <div class="actions-row" style="margin-top:20px">${btn("Save draft", { kind: "primary", icon: "next", attrs: 'type="submit" id="save-btn"' })}${btn("Export gold set", { icon: "arrow", attrs: 'type="button" id="export-btn"' })}</div>
        </form>
      </section>` : notice("Writing to the gold set is for admins.", "attention")}`);

    document.getElementById("export-btn")?.addEventListener("click", () => download("gold/export"));
    let editing = null;

    const form = document.getElementById("gold-form");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = new FormData(form);
        const author = String(f.get("author") || "").trim();
        if (!author) return toast("Enter your name: an entry is written by a person.");
        const body = {
          session: s.id, title: f.get("title"), framework: f.get("framework"), source_ref: f.get("source_ref"),
          config: f.get("config"), controls: f.getAll("controls"), author,
        };
        try {
          if (editing) await post(`gold/${editing}`, body); else await post("gold", body);
          remember(author);
          toast(editing ? "Entry updated and returned to draft." : "Draft saved.", true);
          c.reload();
        } catch (err) { toast(err.message); }
      });
    }

    const show = async (id) => {
      const panel = document.getElementById("entry-panel");
      const e = await api(`gold/${id}`);
      app.querySelectorAll("tr[data-id]").forEach((tr) => tr.setAttribute("aria-selected", String(tr.dataset.id === String(id))));
      const checked = e.review_check;
      panel.innerHTML = `
        <div class="entry">
          <div class="block-head"><h3 style="font-size:15px">No. ${e.id}: ${esc(e.title)}</h3><p>${stateOfEntry(e)}</p></div>
          <dl class="titleblock" style="border:1px solid var(--hair);margin-bottom:16px">
            <div><dt>Source</dt><dd>${esc(e.framework)}. ${esc(e.source_ref)}</dd></div>
            <div><dt>Controls exercised</dt><dd class="mono">${e.controls.map(esc).join("<br>") || "none named yet"}</dd></div>
            <div><dt>Written by</dt><dd>${esc(e.author)}, ${esc(when(e.created_at))}</dd></div>
            ${e.reviewer ? `<div><dt>Signed off by</dt><dd>${esc(e.reviewer)}, ${esc(when(e.reviewed_at))}${e.review_note ? `<br>${esc(e.review_note)}` : ""}</dd></div>` : ""}
          </dl>
          <details class="more"><summary>${c.ICON.chevron} The configuration</summary><pre class="json">${esc(JSON.stringify(e.config, null, 2))}</pre></details>
          <div id="check-out" style="margin:16px 0"></div>
          <div class="actions-row">
            ${btn("Run the rule check", { icon: "play", attrs: 'type="button" id="check-btn"' })}
            ${admin && e.status === "draft" ? btn("Mark authored", { kind: "primary", icon: "next", attrs: 'type="button" id="authored-btn"' }) : ""}
            ${admin && e.status !== "reviewed" ? btn("Edit in the form", { attrs: 'type="button" id="edit-btn"' }) : ""}
          </div>
          ${checked ? `<p class="faint" style="font-size:13px;margin-top:12px">Checked at sign-off: ${checked.resources} resources, ${checked.findings.length} findings, ${checked.criticals.length} critical.</p>` : ""}
          ${admin && e.status === "authored" ? `
            <form id="review-form" class="decision" style="margin-top:24px" novalidate>
              <h4 class="sub" style="margin-top:0">Instructor sign-off</h4>
              <p class="faint" style="font-size:13px;max-width:72ch">Freezes the entry. The reviewer must be someone other than the author, and the rule floor must raise no CRITICAL.</p>
              <label class="field" style="max-width:320px">Reviewer<input name="reviewer" aria-label="Reviewer" maxlength="80"></label>
              <label class="field">Note<textarea name="note" aria-label="Note" rows="2" maxlength="2000"></textarea></label>
              <label class="check"><input type="checkbox" name="confirm"> This is my own sign-off</label>
              <div>${btn("Sign off", { kind: "primary", icon: "next", attrs: 'type="submit"' })}</div>
            </form>` : ""}
        </div>`;
      document.getElementById("check-btn").addEventListener("click", async () => {
        const out = document.getElementById("check-out");
        try {
          const r = await post(`gold/${id}/check`, { session: s.id });
          out.innerHTML = r.criticals.length
            ? notice(`${r.criticals.length} CRITICAL finding(s) on a configuration that should be compliant: a false positive or an error in the control encoding. ${r.criticals.map((f) => `<span class="mono">${esc(f.address)} ${esc(f.rule)}</span>`).join(", ")}`, "error")
            : notice(`${r.resources} resources checked, ${r.findings.length} finding${r.findings.length === 1 ? "" : "s"}, no CRITICAL. Single-resource rules only.`);
        } catch (err) { out.innerHTML = notice(esc(err.message), "error"); }
      });
      document.getElementById("authored-btn")?.addEventListener("click", async () => {
        try { await post(`gold/${id}/authored`, { session: s.id }); toast("Marked authored.", true); c.reload(); } catch (err) { toast(err.message); }
      });
      document.getElementById("edit-btn")?.addEventListener("click", () => {
        editing = id;
        form.elements.title.value = e.title;
        form.elements.framework.value = e.framework;
        form.elements.source_ref.value = e.source_ref;
        form.elements.config.value = JSON.stringify(e.config, null, 2);
        form.querySelectorAll("[name=controls]").forEach((x) => { x.checked = e.controls.includes(x.value); });
        document.getElementById("form-title").textContent = `Edit entry ${id}`;
        document.getElementById("save-btn").querySelector("span").textContent = "Save changes";
        form.scrollIntoView({ block: "start" });
      });
      document.getElementById("review-form")?.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const f = new FormData(ev.target);
        const reviewer = String(f.get("reviewer") || "").trim();
        if (!reviewer) return toast("Enter the reviewer's name.");
        if (!ev.target.querySelector("[name=confirm]").checked) return toast("Tick the box to confirm this is your own sign-off.");
        try {
          await post(`gold/${id}/review`, { session: s.id, reviewer, note: f.get("note"), confirm: true });
          toast("Signed off and frozen.", true);
          c.reload();
        } catch (err) { toast(err.message); }
      });
    };
    app.querySelectorAll("tr[data-id]").forEach((tr) => {
      const open = () => show(Number(tr.dataset.id)).catch((err) => toast(err.message));
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (ev) => ev.key === "Enter" && open());
    });
  }

  return { viewControls, viewGold };
}
