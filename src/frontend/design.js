// KG 013 new design: state the workload, get a candidate configuration.
// Every axis must be stated. A plain-English statement can fill axes, each with the quotation
// that grounds it, but the operator confirms the form; nothing runs from the statement alone.

export function makeDesignView(c) {
  const { esc, btn, state, notice, head, api, post, toast, getSession, meta, titleCase, drawIntent, watchJob, app } = c;
  const pretty = (s) => String(s).replace(/_/g, " ");
  const ACRONYMS = { az_spread: "AZ spread", iam_shape: "IAM shape" };
  const label = (axis) => ACRONYMS[axis] || titleCase(pretty(axis));

  return async function viewDesign(ui) {
    const s = getSession();
    const [m, jobs] = await Promise.all([meta(true), api(`jobs?session=${s.id}`)]);
    const axes = Object.entries(m.design_axes);
    const params = m.jobs.design.params;
    const values = Object.fromEntries(axes.map(([axis]) => [axis, ""]));
    const extracted = new Set(); // axes whose value came from the statement
    let audience = m.audiences[0];
    const canLive = s.role === "admin" && m.live_enabled;

    ui.mount(`
      ${head(13, "New design", "State the workload and get a candidate configuration, with the reason each choice stands.")}
      <div class="run-form">
        <div>
          <section class="block">
            <div class="block-head"><h2>Describe the workload</h2><p>Optional. The model fills only what the text says, and quotes it.</p></div>
            <label class="field">Statement
              <textarea id="statement" aria-label="Workload statement" rows="4" maxlength="2000" placeholder="A payments API for card data in eu-west-1, spread over two availability zones, kept small."></textarea>
              <small id="stmt-count">0 of 2000 characters</small>
            </label>
            <div style="margin-top:12px">${btn("Read statement", { icon: "arrow", attrs: 'id="read-btn" type="button"' })}</div>
            <div id="extract-note" style="margin-top:12px"></div>
          </section>
          <section class="block">
            <div class="block-head"><h2>Intent</h2><p id="axes-left"></p></div>
            <div class="axes">
              ${axes.map(([axis, options]) => `
                <label class="field" data-axis="${esc(axis)}">${esc(label(axis))}
                  <select name="${esc(axis)}" aria-label="${esc(label(axis))}" aria-describedby="ev-${esc(axis)}">
                    <option value="">Choose</option>
                    ${options.map((o) => `<option value="${esc(o)}">${esc(pretty(o))}</option>`).join("")}
                  </select>
                  <small class="evidence" id="ev-${esc(axis)}"></small>
                </label>`).join("")}
            </div>
          </section>
          <section class="block">
            <div class="block-head"><h2>Audience</h2><p>Changes the rendering only; the claims stay identical</p></div>
            <div class="segmented" role="group" aria-label="Audience">
              ${m.audiences.map((a) => `<button type="button" aria-pressed="${a === audience}" data-audience="${esc(a)}">${esc(titleCase(a))}</button>`).join("")}
            </div>
          </section>
          <section class="block">
            <details class="more"><summary>${c.ICON.chevron} Corpus size and seed</summary>
              <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:16px">
                <label class="field" style="width:160px">Corpus size<input id="f-count" inputmode="numeric" value="${esc(params.count.default)}"><small>${esc(params.count.low)} to ${esc(params.count.high)}</small></label>
                <label class="field" style="width:200px">Seed<input id="f-seed" inputmode="numeric" value="${esc(params.seed.default)}"></label>
              </div>
              <p class="faint" style="font-size:13px;margin-top:12px;max-width:70ch">The recommender is fitted on this corpus before it audits the design. A recorded model review exists only for the designs it was recorded on, so a new design runs the rule floor unless an admin calls the model live.</p>
            </details>
          </section>
        </div>
        <aside class="run-side">
          <div class="actions">
            <label class="check" id="confirm-row" hidden><input type="checkbox" id="f-confirm"> I checked the quoted text beside each value the model filled</label>
            ${btn("Run design", { kind: "primary", icon: "play", attrs: 'id="run-btn" disabled' })}
            ${s.role === "admin" ? `<label class="check"><input type="checkbox" id="f-live" ${canLive ? "" : "disabled"}> Call Gemini live (spends budget)</label>
              ${canLive ? "" : `<span class="faint" style="font-size:13px">Live calls are off. An admin can enable them in <a href="#/admin/cloud">${c.kg(26)}</a>.</span>`}` : ""}
          </div>
          <figure class="seed-plot"><svg class="plot" id="intent-plot" role="img" aria-label="Intent ring"></svg><figcaption id="intent-caption" class="faint"></figcaption></figure>
          <div id="job-panel"></div>
        </aside>
      </div>`);

    const runBtn = document.getElementById("run-btn");
    const panel = document.getElementById("job-panel");

    const missing = () => axes.map(([a]) => a).filter((a) => !values[a]);
    const refresh = () => {
      const gap = missing();
      drawIntent(document.getElementById("intent-plot"), axes, values);
      document.getElementById("intent-caption").textContent =
        "One spoke per axis. A tick moves outward as you pick later options in a list, which is an order and not a score. An unstated axis stays dim on the outer ring.";
      document.getElementById("axes-left").textContent = gap.length
        ? `${gap.length} of ${axes.length} still to state: ${gap.map(label).join(", ")}`
        : `All ${axes.length} stated`;
      const confirmRow = document.getElementById("confirm-row");
      confirmRow.hidden = extracted.size === 0;
      const confirmed = extracted.size === 0 || document.getElementById("f-confirm").checked;
      runBtn.disabled = gap.length > 0 || !confirmed || runBtn.classList.contains("busy");
    };

    const setEvidence = (axis, quote) => {
      const field = app.querySelector(`[data-axis="${axis}"]`);
      field.classList.toggle("extracted", Boolean(quote));
      document.getElementById(`ev-${axis}`).textContent = quote ? `From the text: "${quote}"` : "";
    };

    app.querySelectorAll("select[name]").forEach((select) =>
      select.addEventListener("change", () => {
        values[select.name] = select.value;
        extracted.delete(select.name); // stated by the operator now, not by the model
        setEvidence(select.name, "");
        document.getElementById("f-confirm").checked = false;
        refresh();
      }),
    );
    app.querySelectorAll("[data-audience]").forEach((b) =>
      b.addEventListener("click", () => {
        audience = b.dataset.audience;
        app.querySelectorAll("[data-audience]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      }),
    );
    document.getElementById("f-confirm").addEventListener("change", refresh);
    const statement = document.getElementById("statement");
    statement.addEventListener("input", () => {
      document.getElementById("stmt-count").textContent = `${statement.value.length} of 2000 characters`;
    });

    const readBtn = document.getElementById("read-btn");
    readBtn.addEventListener("click", async () => {
      const note = document.getElementById("extract-note");
      if (!statement.value.trim()) return toast("Write a statement first, or choose each axis below.");
      readBtn.disabled = true;
      note.innerHTML = '<div class="skeleton" style="height:44px;max-width:72ch"></div>';
      try {
        const got = await post("design/extract", { session: s.id, statement: statement.value });
        if (!ui.isLive()) return;
        const filled = [];
        for (const [axis] of axes) {
          const f = got.fields[axis];
          // The operator's own choice is never overwritten; a value from an earlier reading is.
          if (!f.value || (values[axis] && !extracted.has(axis))) continue;
          values[axis] = f.value;
          extracted.add(axis);
          app.querySelector(`select[name="${axis}"]`).value = f.value;
          setEvidence(axis, f.evidence);
          filled.push(axis);
        }
        document.getElementById("f-confirm").checked = false;
        const dropped = Object.entries(got.rejected);
        const how = got.live ? "Called Gemini live" : "Replayed a recorded response";
        if (got.llm_status === "missing_fixture") {
          note.innerHTML = notice("No recorded response exists for this statement, so nothing was filled. An admin can switch on live calls in KG 026, or you can choose each axis below.", "attention");
        } else if (got.llm_status !== "ok") {
          note.innerHTML = notice(`The model answered in a form that could not be read (${esc(got.llm_status.replace(/_/g, " "))}). Nothing was filled.`, "attention");
        } else {
          note.innerHTML = notice(
            `${esc(how)}. ${filled.length} of ${axes.length} axes grounded in the text. Read the quotation beside each one.` +
              (dropped.length ? ` Dropped: ${dropped.map(([a, why]) => `${esc(label(a))} (${esc(why)})`).join(", ")}.` : ""),
          );
        }
        refresh();
      } catch (err) {
        if (ui.isLive()) note.innerHTML = notice(esc(err.message), "error");
      } finally {
        readBtn.disabled = false;
      }
    });

    const active = jobs.find((j) => j.kind === "design" && (j.status === "running" || j.status === "queued"));
    if (active) watchJob(ui, active.id, panel, runBtn);
    runBtn.addEventListener("click", async () => {
      const live = document.getElementById("f-live");
      runBtn.disabled = true;
      try {
        const job = await post("jobs", {
          session: s.id,
          kind: "design",
          params: {
            ...values,
            audience,
            count: document.getElementById("f-count").value,
            seed: document.getElementById("f-seed").value,
            ...(live && live.checked ? { live: true } : {}),
          },
        });
        if (ui.isLive()) watchJob(ui, job.id, panel, runBtn);
      } catch (err) {
        panel.innerHTML = notice(esc(err.message), "error");
        refresh();
      }
    });
    refresh();
  };
}
