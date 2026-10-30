/* Labelset — labeler dashboard: claim, submit, track earnings */
(function () {
  "use strict";
  const user = UI.requireLabeler();
  if (!user) return;
  UI.renderShell("labeler");

  const esc = UI.esc, money = UI.money;
  const view = document.getElementById("labeler-view");
  let tab = "assigned";
  let typeFilter = "all";

  const db = () => Store.read();
  const my = () => db().tasks.filter(t => t.labelerId === user.id);
  const orgName = id => (db().orgs.find(o => o.id === id) || {}).name || "—";
  const projectName = id => (db().projects.find(p => p.id === id) || {}).title || "—";

  document.getElementById("labeler-title").textContent = `Welcome, ${user.name.split(" ")[0]}`;
  document.getElementById("labeler-sub").textContent = `Skills: ${user.skills.join(", ") || "General"} · ${user.email}`;

  UI.tabs(document.getElementById("labeler-tabs"), t => { tab = t; render(); });

  function render() {
    const d = db();
    const mine = my();
    const approved = mine.filter(t => t.status === "approved");
    const earned = approved.reduce((s, t) => s + t.reward, 0);
    const inReview = mine.filter(t => t.status === "submitted");
    const assigned = mine.filter(t => t.status === "assigned" || t.status === "rejected");
    const available = d.tasks.filter(t => t.status === "available");

    setCount("cnt-assigned", assigned.length);
    setCount("cnt-submitted", inReview.length);
    setCount("cnt-available", available.length);

    document.getElementById("labeler-stats").innerHTML = `
      ${stat(money(user.balance || 0), "Available balance")}
      ${stat(money(earned), "Verified earnings")}
      ${stat(approved.length, "Tasks paid out")}
      ${stat(inReview.length, "Awaiting verification")}`;

    if (tab === "assigned") renderAssigned(assigned);
    else if (tab === "submitted") renderSubmitted(inReview);
    else if (tab === "available") renderMarket(available, d);
    else renderHistory(approved, mine);
  }

  const setCount = (id, n) => { const el = document.getElementById(id); el.hidden = !n; el.textContent = n; };
  const stat = (v, l) => `<div class="stat-card"><p class="stat-card__value ${typeof v === "string" && v.startsWith("$") ? "stat-card__value--accent" : ""}">${v}</p><p class="stat-card__label">${l}</p></div>`;

  /* ---------- assigned / rejected ---------- */
  function renderAssigned(list) {
    view.innerHTML = list.length ? list.map(t => {
      const rejected = t.status === "rejected";
      return `<div class="task-row">
        <div class="task-row__main">
          <strong>${esc(t.question)}</strong>
          <span>${esc(orgName(t.orgId))} · ${esc(projectName(t.projectId))} · pays ${money(t.reward)}</span>
          ${rejected ? `<div class="review-quote" style="border-color:var(--red)">Returned by reviewer: ${esc(t.reviewNote)} — fix and resubmit.</div>` : ""}
        </div>
        <div class="task-row__side">${UI.badge(t.status)}
          <button class="button button--primary button--sm" data-open="${t.id}">${rejected ? "Fix &amp; resubmit" : "Open &amp; label"}</button>
        </div>
      </div>`;
    }).join("") : empty("No open tasks", "Claim one from the Task market and it appears here.");
    view.querySelectorAll("[data-open]").forEach(b => b.addEventListener("click", () => openTask(b.dataset.open)));
  }

  /* ---------- labeling modal ---------- */
  function openTask(taskId) {
    const t = db().tasks.find(x => x.id === taskId);
    if (!t) return;
    const modal = document.createElement("div");
    modal.className = "modal-backdrop";
    modal.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-label="Label task">
        <div class="modal__head"><strong>${esc(t.question)}</strong><button class="modal__x" aria-label="Close">×</button></div>
        <p class="form-note" style="margin-bottom:1rem">${esc(orgName(t.orgId))} · ${esc(projectName(t.projectId))} · pays ${money(t.reward)} after verification</p>
        <div class="mock-media mock-media--${t.question.startsWith("Audio") ? "audio" : t.question.startsWith("Video") ? "video" : "image"}">
          ${t.question.startsWith("Audio") ? "🎧 Audio clip · 0:42" : t.question.startsWith("Video") ? "🎬 Video clip · 1:15" : "🖼️ Image · 1920×1080"}
        </div>
        <fieldset style="border:0;margin:1.2rem 0 .4rem">
          <legend style="font-size:.85rem;font-weight:600;margin-bottom:.6rem">Choose the correct label</legend>
          ${t.options.map((o, i) => `
            <label class="choice"><input type="radio" name="answer" value="${esc(o)}" ${t.answer === o ? "checked" : ""}/> ${esc(o)}</label>`).join("")}
        </fieldset>
        <div class="field"><label for="m-note">Note for the reviewer (optional)</label><textarea id="m-note" rows="2" placeholder="Anything the reviewer should know…">${esc(t.note || "")}</textarea></div>
        <div style="display:flex;gap:.8rem;justify-content:end">
          <button class="button button--ghost" data-close>Cancel</button>
          <button class="button button--primary" data-submit>Submit for review</button>
        </div>
        <p class="form-status" id="m-status" role="status"></p>
      </div>`;
    document.body.appendChild(modal);

    const close = () => modal.remove();
    modal.querySelector(".modal__x").addEventListener("click", close);
    modal.querySelector("[data-close]").addEventListener("click", close);
    modal.addEventListener("click", e => { if (e.target === modal) close(); });

    modal.querySelector("[data-submit]").addEventListener("click", () => {
      const answer = modal.querySelector('input[name="answer"]:checked');
      const st = modal.querySelector("#m-status");
      if (!answer) { st.textContent = "Pick a label first."; st.className = "form-status is-error"; return; }
      const d = Store.read();
      const task = d.tasks.find(x => x.id === taskId);
      task.answer = answer.value;
      task.note = modal.querySelector("#m-note").value.trim();
      task.status = "submitted";
      task.submittedAt = new Date().toISOString();
      Store.write(d);
      const owner = (d.orgs.find(x => x.id === task.orgId) || {}).ownerId;
      if (owner) Store.notify(owner, `A task was submitted for review: ${task.question}`, "review");
      close();
      render();
    });
  }

  /* ---------- submitted ---------- */
  function renderSubmitted(list) {
    view.innerHTML = list.length ? list.map(t => `
      <div class="task-row">
        <div class="task-row__main"><strong>${esc(t.question)}</strong>
          <span>${esc(orgName(t.orgId))} · submitted ${Store.fmtAgo(t.submittedAt)} · answer: ${esc(t.answer)}</span></div>
        <div class="task-row__side">${UI.badge(t.status)}<span class="form-note">pays ${money(t.reward)} on verification</span></div>
      </div>`).join("") : empty("Nothing in review", "Submitted tasks wait here until the organization verifies them.");
  }

  /* ---------- market ---------- */
  function renderMarket(list, d) {
    const types = ["all", "Audio", "Image", "Video"];
    const filtered = typeFilter === "all" ? list : list.filter(t => projectNameType(t) === typeFilter);
    view.innerHTML = `
      <div class="card__head">
        <h3>Open tasks (${filtered.length})</h3>
        <div style="display:flex;gap:.4rem">${types.map(x => `<button class="mini-btn" data-type="${x}" ${typeFilter === x ? 'style="background:var(--primary);color:#fff"' : ""}>${x}</button>`).join("")}</div>
      </div>
      ${filtered.length ? filtered.slice(0, 30).map(t => `
        <div class="task-row">
          <div class="task-row__main"><strong>${esc(t.question)}</strong>
            <span>${esc(orgName(t.orgId))} · ${esc(projectName(t.projectId))}</span></div>
          <div class="task-row__side"><span class="amount">${money(t.reward)}</span>
            <button class="button button--primary button--sm" data-claim="${t.id}">Claim task</button></div>
        </div>`).join("") : empty("No open tasks", "Check back soon — new batches drop weekly.")}
    `;
    view.querySelectorAll("[data-type]").forEach(b => b.addEventListener("click", () => { typeFilter = b.dataset.type; render(); }));
    view.querySelectorAll("[data-claim]").forEach(b => b.addEventListener("click", () => {
      const d2 = Store.read();
      const t = d2.tasks.find(x => x.id === b.dataset.claim);
      t.status = "assigned"; t.labelerId = user.id; t.assignedAt = new Date().toISOString();
      Store.write(d2);
      openTask(t.id);
      render();
    }));
  }
  const projectNameType = t => (db().projects.find(p => p.id === t.projectId) || {}).type || "";

  /* ---------- history ---------- */
  function renderHistory(approved, mine) {
    const rows = [...mine].sort((a, b) => (b.reviewedAt || b.submittedAt || "") > (a.reviewedAt || a.submittedAt || "") ? -1 : 1);
    view.innerHTML = rows.length ? `<table class="table"><thead><tr><th>Task</th><th>Organization</th><th>Status</th><th>Reward</th><th>Reviewed</th></tr></thead><tbody>
      ${rows.map(t => `<tr>
        <td style="max-width:280px">${esc(t.question)}</td>
        <td class="muted">${esc(orgName(t.orgId))}</td>
        <td>${UI.badge(t.status)}</td>
        <td class="amount ${t.status === "approved" ? "amount--in" : t.status === "rejected" ? "amount--out" : ""}">${t.status === "approved" ? "+" + money(t.reward) : money(t.reward)}</td>
        <td class="muted">${t.reviewedAt ? Store.fmtDate(t.reviewedAt) : "—"}</td>
      </tr>`).join("")}
    </tbody></table>` : empty("No history yet", "Your completed and verified tasks will be listed here.");
  }

  const empty = (t, s) => `<p class="empty"><strong>${t}</strong>${s}</p>`;

  render();
})();
