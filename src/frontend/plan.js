// KG 014 plan and apply: a dry-run diff of a stored run's spec, then an apply that needs it.
// Every figure is read from the stored plan; this file renders, it does not compute.

export function makePlanView(c) {
  const { esc, btn, state, sev, notice, head, api, post, toast, getSession, meta, kg, when, titleCase, drawEstate, watchJob, app } = c;
  const money = (n) => `${n >= 0 ? "+" : "-"}${Math.abs(n).toFixed(2)} USD a month`;
  const tally = (counts) => ["CRITICAL", "HIGH", "MEDIUM", "ADVISORY"].filter((k) => counts[k]).map((k) => `${counts[k]} ${k.toLowerCase()}`).join(", ") || "none";
  const val = (v) => (v === null || v === undefined ? "unset" : typeof v === "object" ? JSON.stringify(v) : String(v));

  // ---- no run chosen: pick one ----
  async function pickRun(ui) {
    const runs = await api("runs");
    if (!runs.length) {
      return ui.mount(`${head(14, "Plan and apply", "Plan a stored run, then apply the plan.")}<div class="empty"><p>No run is stored yet. Design a configuration or review an estate first.</p>${btn("New design", { kind: "primary", attrs: 'data-go="/design"' })}</div>`);
    }
    ui.mount(`
      ${head(14, "Plan and apply", "A plan is a dry-run diff of a run's spec. Nothing changes until you apply it, and an apply needs a plan.")}
      <div class="table-wrap"><table>
        <thead><tr><th>Run</th><th>Recorded</th><th>Kind</th><th>Loop</th><th>Findings</th></tr></thead>
        <tbody>${runs.map((r) => `
          <tr class="link" tabindex="0" data-prefix="${esc(r.prefix)}">
            <td class="mono">${esc(r.prefix)}</td>
            <td>${esc(when(r.created_at))}</td>
            <td>${esc(r.mode === "design" ? "Design" : r.variant || "Review")}</td>
            <td>${state(r.loop_status)}</td>
            <td><span class="strip">${r.severities.map(sev).join("") || '<span class="faint">none</span>'}</span></td>
          </tr>`).join("")}</tbody>
      </table></div>`);
    app.querySelectorAll("tr.link").forEach((tr) => {
      const open = () => ui.go(`/plan/${tr.dataset.prefix}`);
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => e.key === "Enter" && open());
    });
  }

  // ---- one run ----
  return async function viewPlan(ui, prefix) {
    if (!prefix) return pickRun(ui);
    const s = getSession();
    const [run, info, cloud, m] = await Promise.all([api(`runs/${prefix}?light=1`), api(`runs/${prefix}/plans`), api("cloud"), meta(true)]);
    const sum = run.summary;
    const mode = info.mode;
    const loop = sum && sum.loop;
    const lastPass = loop ? loop.passes[loop.passes.length - 1].findings : [];
    const blocked = !loop ? "this run has no stored summary" : loop.status !== "CONVERGED" ? `the advisor loop ended ${loop.status.toLowerCase()} (${loop.reason.toLowerCase()})` : lastPass.some((f) => f.severity === "CRITICAL") ? "a CRITICAL finding is still open" : "";
    const events = info.events.map((e) => e.event);
    const planned = info.plans.length;
    const applied = events.includes("applied");
    const failed = !applied && events[events.length - 1] === "apply_failed";
    const canTerraformPlan = s.role === "admin" && cloud.terraform_installed && mode === "design";
    let backend = "local";

    ui.mount(`
      ${head(14, "Plan and apply", `Run <span class="mono">${esc(run.prefix)}</span>. A plan is a dry-run diff of its spec; an apply needs a plan.`)}
      <ol class="lifecycle" aria-label="Lifecycle of this run">
        <li><b>${mode === "design" ? "Designed" : "Reviewed"}</b>${state("pass", "Stored")}</li>
        <li><b>Planned</b>${planned ? state("pass", `${planned} plan${planned === 1 ? "" : "s"}`) : state("planned", "Not yet")}</li>
        <li><b>Applied</b>${applied ? state("pass", "Applied") : failed ? state("fail", "Last apply failed") : state("planned", "Not yet")}</li>
      </ol>
      <section class="block">
        <div class="sleeve">
          <div class="sleeve-plot">
            ${sum ? `<svg class="plot drawn" id="plan-plot" role="img" aria-label="Estate graph with ${sum.graph.nodes.length} resources"></svg>
              <p class="faint" style="font-size:13px">Select a change below to lift it and everything that depends on it.</p>` : `<div class="empty"><p>This run has no stored estate graph.</p></div>`}
          </div>
          <dl class="titleblock">
            <div><dt>Kind</dt><dd>${esc(mode === "design" ? "Design from a stated intent" : "Review of an observed estate")}</dd></div>
            <div><dt>Loop</dt><dd>${loop ? `${state(loop.status)} <span class="faint">${esc(titleCase(loop.reason))}</span>` : '<span class="faint">unknown</span>'}</dd></div>
            <div><dt>Baseline</dt><dd>${esc(mode === "design" ? "Empty: every resource is a create" : "The observed estate")}</dd></div>
            <div><dt>Run</dt><dd class="mono">${esc(run.prefix)}</dd></div>
            <div><dt>Open the run</dt><dd><a href="#/run/${esc(run.prefix)}">${kg(11)} Run sleeve</a></dd></div>
          </dl>
        </div>
      </section>
      <section class="block">
        <div class="block-head"><h2>Make a plan</h2><p>Reads the stored spec. Changes nothing.</p></div>
        ${blocked ? notice(`This run is not planned: ${esc(blocked)}. A spec with an unresolved finding never reaches a plan (INV-1).`, "attention") : `
          <div class="segmented" role="group" aria-label="Backend">
            <button type="button" data-backend="local" aria-pressed="true">Local diff</button>
            <button type="button" data-backend="terraform" aria-pressed="false" ${canTerraformPlan ? "" : "disabled"}>Terraform, offline</button>
          </div>
          <p class="faint" style="font-size:13px;margin:10px 0 16px;max-width:72ch">${canTerraformPlan ? "Terraform runs the real binary with mock credentials: it validates the document and plans the creates. It cannot touch an account." : esc(!cloud.terraform_installed ? "The Terraform backend needs the terraform binary on this machine." : mode !== "design" ? "The Terraform backend plans a deployment from empty state, so it is for design runs only." : "The Terraform backend is for admins.")}</p>
          <div class="actions-row">${btn("Make plan", { kind: "primary", icon: "play", attrs: 'id="plan-btn"' })}</div>`}
        <div id="job-panel" style="margin-top:16px"></div>
      </section>
      <section class="block" id="plans">
        <div class="block-head"><h2>Plans</h2><p>${planned ? `${planned} stored, newest first` : "None yet"}</p></div>
        ${planned ? [...info.plans].reverse().map((p, i) => planCard(p, i)).join("") : '<div class="empty"><p>No plan has been made for this run.</p></div>'}
      </section>`);

    let plot = null;
    if (sum) plot = drawEstate(document.getElementById("plan-plot"), sum.graph, { labels: document.getElementById("plan-plot").parentElement.clientWidth >= 480 });

    const reload = () => c.reload();
    const panel = document.getElementById("job-panel");
    const submit = async (button, kind, params) => {
      if (button) button.disabled = true;
      try {
        const job = await post("jobs", { session: s.id, kind, params });
        if (ui.isLive()) watchJob(ui, job.id, panel, button || document.createElement("button"), reload);
      } catch (err) {
        if (button) button.disabled = false;
        panel.innerHTML = notice(esc(err.message), "error");
      }
    };

    app.querySelectorAll("[data-backend]").forEach((b) =>
      b.addEventListener("click", () => {
        if (b.disabled) return;
        backend = b.dataset.backend;
        app.querySelectorAll("[data-backend]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      }),
    );
    const planBtn = document.getElementById("plan-btn");
    if (planBtn) planBtn.addEventListener("click", () => submit(planBtn, "plan", { spec: run.prefix, backend }));

    // Selecting a change lifts it and its blast radius on the plot.
    app.querySelectorAll("tr[data-lift]").forEach((tr) => {
      const lift = () => {
        const on = tr.getAttribute("aria-selected") !== "true";
        app.querySelectorAll("tr[data-lift]").forEach((x) => x.setAttribute("aria-selected", "false"));
        tr.setAttribute("aria-selected", String(on));
        if (plot) plot.highlight(on ? JSON.parse(tr.dataset.lift) : null, "INK");
      };
      tr.addEventListener("click", lift);
      tr.addEventListener("keydown", (e) => e.key === "Enter" && lift());
    });

    app.querySelectorAll("[data-apply-local]").forEach((b) =>
      b.addEventListener("click", () => submit(b, "apply", { plan: b.dataset.applyLocal, backend: "local" })),
    );
    app.querySelectorAll("[data-gated]").forEach((box) => {
      const planId = box.dataset.gated;
      const typed = box.querySelector("input[type=text]");
      const budgets = box.querySelector("input[type=checkbox]");
      const go = box.querySelector("button.btn");
      const ready = box.dataset.ready === "true";
      const check = () => { go.disabled = !(ready && typed.value === planId && budgets.checked); };
      typed.addEventListener("input", check);
      budgets.addEventListener("change", check);
      go.addEventListener("click", () => submit(go, "apply", { plan: planId, backend: "terraform", confirm: typed.value, budgets_applied: true }));
      check();
    });

    function planCard({ plan, apply, preflight }, index) {
      const cov = plan.coverage;
      const rows = [
        ...plan.creates.map((a) => ({ sym: "+", address: a, lift: [a], detail: "" })),
        ...plan.modifies.map((mod) => ({ sym: "~", address: mod.address, lift: [mod.address, ...(plan.blast_radius[mod.address] || [])], detail: mod.changes.map((ch) => `${esc(ch.attribute)}: ${esc(val(ch.before))} -> ${esc(val(ch.after))}`).join("<br>") })),
        ...plan.destroys.map((a) => ({ sym: "-", address: a, lift: [a, ...(plan.blast_radius[a] || [])], detail: "" })),
      ];
      const cost = plan.cost;
      const grouped = {};
      if (cost.available) for (const note of [...cost.spec.not_priced, ...cost.spec.excluded]) {
        const at = note.indexOf(": ");
        (grouped[note.slice(at + 2)] ||= []).push(note.slice(0, at));
      }
      const tf = plan.terraform;
      return `
        <article class="plan-card" ${index === 0 ? "" : 'style="margin-top:40px"'}>
          <div class="block-head"><h3 style="font-size:15px">Plan <span class="mono">${esc(plan.plan_id)}</span></h3><p>${esc(plan.backend)} backend, baseline ${esc(plan.baseline_kind)}</p></div>
          <dl class="titleblock" style="border:1px solid var(--hair);margin-bottom:20px">
            <div><dt>Changes</dt><dd class="mono">create ${plan.creates.length}, modify ${plan.modifies.length}, destroy ${plan.destroys.length}</dd></div>
            <div><dt>Findings in the spec</dt><dd>${esc(tally(cov.before))} before, ${esc(tally(cov.after))} after${cov.introduced.length ? ` <span class="faint">(${cov.introduced.length} introduced)</span>` : ""}</dd></div>
          </dl>
          <div class="table-wrap"><table class="diff">
            <thead><tr><th class="sym"></th><th>Resource</th><th>What changes</th></tr></thead>
            <tbody>${rows.map((r) => `<tr class="link" tabindex="0" data-lift="${esc(JSON.stringify(r.lift))}"><td class="sym">${r.sym}</td><td class="mono">${esc(r.address)}</td><td class="mono faint">${r.detail || (r.sym === "+" ? "new" : "")}</td></tr>`).join("") || '<tr><td colspan="3" class="faint">No changes.</td></tr>'}</tbody>
          </table></div>
          ${cov.fixed.length ? `<p style="margin:16px 0 0;font-size:14px">Fixed by this plan: ${cov.fixed.map((f) => `${sev(f.severity)}<span class="mono">${esc(f.address)}</span> <span class="faint">${esc(f.rule)}</span>`).join(", ")}</p>` : ""}
          <h4 class="sub">Cost</h4>
          ${cost.available ? `
            <p><span class="delta">${esc(money(cost.delta_usd))}</span></p>
            <p class="faint" style="font-size:13px;max-width:72ch">${esc(cost.note)} Prices retrieved ${esc(cost.spec.retrieved_at)} from the AWS Price List, region ${esc(cost.spec.region)}.</p>
            ${Object.keys(grouped).length ? `<details class="more"><summary>${c.ICON.chevron} Not in the figure</summary><ul class="notes">${Object.entries(grouped).map(([why, addrs]) => `<li>${esc(why)} <span class="mono faint">${esc(addrs.join(", "))}</span></li>`).join("")}</ul></details>` : ""}`
            : `<p class="faint">Not available: ${esc(cost.reason)}</p>`}
          ${tf ? `
            <h4 class="sub">Terraform ${esc(tf.version)}, offline</h4>
            <p style="font-size:14px">Validated and planned ${tf.creates.length} creates with mock credentials. It cannot reach an account.${tf.creates.length !== plan.creates.length ? ` That is ${tf.creates.length - plan.creates.length} more than the spec, because the added resources below are needed for the document to be valid.` : ""}</p>
            <details class="more"><summary>${c.ICON.chevron} Added to make the document valid (${tf.overlay.length})</summary><ul class="notes">${tf.overlay.map((o) => `<li class="mono">${esc(o)}</li>`).join("")}</ul></details>
            ${tf.caveats.length ? `<details class="more"><summary>${c.ICON.chevron} May still fail to apply (${tf.caveats.length})</summary><ul class="notes">${tf.caveats.map((o) => `<li class="mono">${esc(o)}</li>`).join("")}</ul></details>` : ""}` : ""}
          <h4 class="sub">Apply</h4>
          ${applyBlock(plan, apply, preflight)}
        </article>`;
    }

    function applyBlock(plan, apply, preflight) {
      if (apply) {
        return `
          <p>${apply.status === "applied" ? state("pass", "Applied") : state("fail", "Failed")} <span class="faint">${apply.simulated ? "Simulated into the local store; nothing left this machine." : `Real apply, account ending ${esc(apply.account_suffix)}.`}</span></p>
          ${apply.error ? notice(esc(apply.error), "error") : ""}
          ${apply.steps ? `<div class="table-wrap"><table><thead><tr><th>Status</th><th>Action</th><th>Resource</th></tr></thead><tbody>${apply.steps.map((st) => `<tr><td>${state(st.status === "done" ? "pass" : st.status === "failed" ? "fail" : "planned", titleCase(st.status.replace(/_/g, " ")))}</td><td>${esc(st.action)}</td><td class="mono">${esc(st.address)}</td></tr>`).join("")}</tbody></table></div>` : ""}
          ${apply.state_path ? `<p class="faint" style="font-size:13px">State: <span class="mono">${esc(apply.state_path)}</span><br>Teardown, shown and never run: <span class="mono">${esc(apply.teardown_command)}</span></p>` : ""}`;
      }
      if (plan.backend === "local") {
        return `<p class="faint" style="font-size:13px;max-width:72ch;margin-bottom:12px">A simulated apply writes the planned state into the local artifact store. Nothing leaves this machine, and it enforces the same rules: one apply per plan, and the spec must be unchanged since it was planned.</p>${btn("Apply the plan, simulated", { kind: "primary", icon: "play", attrs: `data-apply-local="${esc(plan.plan_id)}"` })}`;
      }
      if (s.role !== "admin") return notice("A real apply is for admins. Switch to the admin role on the cover.", "attention");
      const grant = preflight ? preflight.offenders.length === 0 : false;
      const gates = [
        ["Admin session", true, ""],
        ["Live mode is on (KG 026)", m.live_enabled, m.live_enabled ? "" : "Off. It resets on every server restart."],
        ["terraform is installed", cloud.terraform_installed, cloud.terraform_version || ""],
        ["The write role covers this plan", grant, grant ? `Grants ${(preflight.granted || []).join(", ")}` : `Missing: ${(preflight?.offenders || ["unknown"]).join("; ")}`],
        ["Role and account are configured on the server", cloud.apply.role_configured && cloud.apply.account_configured, "KGCR_PROVISION_ROLE_ARN and KGCR_APPLY_ACCOUNT_ID"],
      ];
      const ready = gates.every((g) => g[1]);
      return `
        ${notice("This path is authored and unit tested against fakes. This project has never run it against AWS: there are no credentials on the build machine. It creates real resources that cost money. It re-plans against the live provider and refuses unless the result equals the plan above.", "attention")}
        <ul class="gates" style="margin:16px 0">${gates.map(([label, ok, why]) => `<li><span>${esc(label)}${why ? ` <span class="faint">${esc(why)}</span>` : ""}</span>${ok ? state("pass", "Met") : state("fail", "Not met")}</li>`).join("")}</ul>
        <div class="confirm" data-gated="${esc(plan.plan_id)}" data-ready="${ready}">
          <label class="field">Type the plan id to confirm<input type="text" autocomplete="off" placeholder="${esc(plan.plan_id)}" aria-label="Plan id to confirm"></label>
          <label class="check"><input type="checkbox"> The budget alarms in src/aws/budgets.tf are applied</label>
          <div>${btn("Apply to AWS", { kind: "spend", icon: "spend", attrs: "disabled" })}</div>
        </div>`;
    }
  };
}
