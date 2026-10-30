/* Labelset — organization dashboard: data, projects, tasks, review, team */
(function () {
  "use strict";
  const ctx = UI.requireOrg();
  if (!ctx) return;
  const { user } = ctx;
  UI.renderShell("org");

  const esc = UI.esc, money = UI.money;
  const view = document.getElementById("org-view");
  let tab = "overview";

  function org() { return Store.read().orgs.find(o => o.id === ctx.org.id); }
  const isOwner = () => org().ownerId === user.id;
  function db() { return Store.read(); }
  const orgTasks = () => db().tasks.filter(t => t.orgId === ctx.org.id);
  const projectName = id => (db().projects.find(p => p.id === id) || {}).title || "—";
  const userById = id => db().users.find(u => u.id === id);

  /* ---------- header ---------- */
  const o = org();
  document.getElementById("org-title").textContent = o.name;
  document.getElementById("org-sub").textContent = `Org code ${o.code} · owned by ${esc(userById(o.ownerId).name)}`;
  document.getElementById("quick-upload").addEventListener("click", () => {
    document.querySelector('[data-tab="data"]').click();
  });

  UI.tabs(document.getElementById("org-tabs"), t => { tab = t; render(); });

  function render() {
    const submitted = orgTasks().filter(t => t.status === "submitted").length;
    const rc = document.getElementById("tab-review-count");
    rc.hidden = !submitted; rc.textContent = submitted;

    ({ overview, data, projects, tasks, team })[tab]();
    view.querySelectorAll("form").forEach(f => f.addEventListener("submit", handleForm));
  }

  /* ================= OVERVIEW ================= */
  function overview() {
    const d = db();
    const t = orgTasks();
    const spend = d.payments.filter(p => p.orgId === o.id && p.type === "payout").reduce((s, p) => s + p.amount, 0);
    const recent = [...t].sort((a, b) => (b.reviewedAt || b.submittedAt || b.assignedAt || "") > (a.reviewedAt || a.submittedAt || a.assignedAt || "") ? -1 : 1).slice(0, 6);

    view.innerHTML = `
      <div class="grid grid--stats" style="margin-bottom:1.6rem">
        ${stat(d.datasets.filter(x => x.orgId === o.id).length, "Datasets")}
        ${stat(d.projects.filter(x => x.orgId === o.id).length, "Projects")}
        ${stat(submittedBadge(), "Awaiting your review")}
        ${stat(money(o.balance), "Prepaid balance")}
      </div>
      <div class="grid grid--2">
        <div class="card">
          <div class="card__head"><h3>Recent task activity</h3><button class="mini-btn" data-goto="tasks">Open tasks</button></div>
          ${recent.length ? recent.map(t2 => `
            <div class="task-row">
              <div class="task-row__main"><strong>${esc(t2.question)}</strong>
                <span>${esc(projectName(t2.projectId))} · ${t2.labelerId ? esc(userById(t2.labelerId).name) : "unassigned"}</span></div>
              <div class="task-row__side">${UI.badge(t2.status)}</div>
            </div>`).join("") : `<p class="empty">No activity yet — create a project to generate tasks.</p>`}
        </div>
        <div class="card">
          <h3 style="margin-bottom:1rem">Spend snapshot</h3>
          <p class="muted" style="margin-bottom:.4rem">Paid out to labelers</p><p class="amount amount--out" style="font-size:1.5rem">${money(spend)}</p>
          <p class="muted" style="margin:.9rem 0 .4rem">Approved tasks</p><p class="amount" style="font-size:1.5rem">${t.filter(x => x.status === "approved").length}</p>
          <hr style="border:0;border-top:1px solid var(--line);margin:1.1rem 0">
          <a class="button button--ghost button--sm" href="billing.html">Manage billing →</a>
        </div>
      </div>`;
    view.querySelectorAll("[data-goto]").forEach(b => b.addEventListener("click", () => document.querySelector(`[data-tab="${b.dataset.goto}"]`).click()));
  }
  const submittedBadge = () => orgTasks().filter(t => t.status === "submitted").length;
  const stat = (v, l) => `<div class="stat-card"><p class="stat-card__value ${typeof v === "string" && v.startsWith("$") ? "stat-card__value--accent" : ""}">${v}</p><p class="stat-card__label">${l}</p></div>`;

  /* ================= DATA ================= */
  function data() {
    const sets = db().datasets.filter(x => x.orgId === o.id);
    view.innerHTML = `
      <div class="grid grid--2">
        <div class="card">
          <h3 style="margin-bottom:1.1rem">Upload a dataset</h3>
          <form id="upload-form">
            <label class="file-drop" id="file-drop" for="file-input">
              <strong>Choose files</strong> or drop them here — WAV/MP3, JPG/PNG, MP4/MOV<br/>
              <span class="form-note" id="file-name">Demo mode: files are registered, not transferred.</span>
              <input type="file" id="file-input" multiple hidden />
            </label>
            <div class="field" style="margin-top:1.2rem"><label for="ds-name">Dataset name</label><input id="ds-name" required placeholder="Warehouse cams October" /></div>
            <div class="form-row">
              <div class="field"><label for="ds-type">Data type</label>
                <select id="ds-type"><option>Audio</option><option selected>Image</option><option>Video</option></select></div>
              <div class="field"><label for="ds-items">Items (files)</label><input id="ds-items" type="number" min="1" value="20" required /></div>
            </div>
            <button class="button button--primary" type="submit">Upload &amp; register</button>
            <p class="form-status" id="upload-status" role="status"></p>
          </form>
        </div>
        <div class="card">
          <div class="card__head"><h3>Datasets (${sets.length})</h3></div>
          ${sets.length ? `<table class="table"><thead><tr><th>Name</th><th>Type</th><th>Items</th><th>Uploaded</th></tr></thead><tbody>
            ${sets.map(s => `<tr><td>${esc(s.name)}</td><td><span class="chip">${s.type}</span></td><td>${s.items}</td><td class="muted">${Store.fmtDate(s.uploadedAt)}</td></tr>`).join("")}
          </tbody></table>` : `<p class="empty"><strong>No datasets yet</strong>Upload audio, image or video data to start a project.`}
        </div>
      </div>`;

    const fi = document.getElementById("file-input");
    fi.addEventListener("change", () => {
      document.getElementById("file-name").textContent = fi.files.length ? `${fi.files.length} file(s) selected: ${fi.files[0].name}${fi.files.length > 1 ? "…" : ""}` : "Demo mode: files are registered, not transferred.";
    });
  }

  /* ================= PROJECTS ================= */
  function projects() {
    const d = db();
    const list = d.projects.filter(p => p.orgId === o.id);
    const sets = d.datasets.filter(x => x.orgId === o.id);
    view.innerHTML = `
      <div class="grid grid--2">
        <div class="card">
          <h3 style="margin-bottom:1.1rem">Create a project</h3>
          <form id="project-form">
            <div class="field"><label for="pj-title">Project title</label><input id="pj-title" required placeholder="Night-time pedestrian tagging" /></div>
            <div class="field"><label for="pj-dataset">Dataset</label>
              <select id="pj-dataset" required>${sets.length ? sets.map(s => `<option value="${s.id}" data-type="${s.type}">${esc(s.name)} · ${s.type} (${s.items} items)</option>`).join("") : `<option value="">Upload a dataset first</option>`}</select></div>
            <div class="form-row">
              <div class="field"><label for="pj-reward">Reward per task ($)</label><input id="pj-reward" type="number" min="0.5" step="0.25" value="2" required /></div>
              <div class="field"><label for="pj-count">Tasks to generate</label><input id="pj-count" type="number" min="1" max="50" value="8" required /></div>
            </div>
            <p class="form-note" style="margin-bottom:1rem">Tasks land in the open pool — labelers claim them, or assign them from the Tasks tab.</p>
            <button class="button button--primary" type="submit" ${sets.length ? "" : "disabled"}>Create project &amp; tasks</button>
            <p class="form-status" id="project-status" role="status"></p>
          </form>
        </div>
        <div class="card">
          <div class="card__head"><h3>Projects (${list.length})</h3></div>
          ${list.length ? list.map(p => {
            const ts = d.tasks.filter(t => t.projectId === p.id);
            const done = ts.filter(t => t.status === "approved").length;
            const pct = ts.length ? Math.round(done / ts.length * 100) : 0;
            return `<div class="task-row">
              <div class="task-row__main"><strong>${esc(p.title)}</strong>
                <span>${p.type} · ${money(p.reward)}/task · ${done}/${ts.length} verified</span>
                <div class="progress" style="margin-top:.5rem;max-width:260px"><i style="width:${pct}%"></i></div></div>
              <div class="task-row__side"><span class="status status--${p.status}">${p.status}</span>
                <button class="mini-btn" data-goto="tasks" data-filter-project="${p.id}">Manage</button></div>
            </div>`;
          }).join("") : `<p class="empty"><strong>No projects yet</strong>Create one from a dataset.</p>`}
        </div>
      </div>`;
    view.querySelectorAll("[data-goto]").forEach(b => b.addEventListener("click", () => {
      if (b.dataset.filterProject) pendingFilter = b.dataset.filterProject;
      document.querySelector(`[data-tab="${b.dataset.goto}"]`).click();
    }));
  }

  /* ================= TASKS + REVIEW ================= */
  let pendingFilter = null;
  let filter = "all";
  function tasks() {
    const d = db();
    const submitted = orgTasks().filter(t => t.status === "submitted");
    if (pendingFilter) { filter = "project:" + pendingFilter; pendingFilter = null; }
    const [fkind, fval] = filter.split(":");
    let list = orgTasks();
    if (fkind === "project") list = list.filter(t => t.projectId === fval);
    else if (fkind !== "all") list = list.filter(t => t.status === fkind);

    const labelers = d.users.filter(u => !d.orgs.some(x => x.ownerId === u.id));
    const chips = ["all", "available", "assigned", "submitted", "approved", "rejected"];

    view.innerHTML = `
      <div class="card" style="margin-bottom:1.6rem">
        <div class="card__head"><h3>Review queue ${submitted.length ? `(${submitted.length})` : ""}</h3>
          <span class="form-note">Approving verifies the work and releases payment to the labeler.</span></div>
        ${submitted.length ? submitted.map(t => {
          const lu = userById(t.labelerId);
          return `<div class="task-row">
            <div class="task-row__main"><strong>${esc(t.question)}</strong>
              <span>${esc(projectName(t.projectId))} · by ${lu ? esc(lu.name) : "?"} · ${money(t.reward)}</span>
              <div class="review-quote">Answer: <strong>${esc(t.answer || "—")}</strong>${t.note ? ` · note: ${esc(t.note)}` : ""}</div></div>
            <div class="task-row__side">
              <button class="button button--primary button--sm" data-approve="${t.id}">Verify &amp; pay</button>
              <button class="button button--ghost button--sm" data-reject="${t.id}">Return</button>
            </div>
          </div>`;
        }).join("") : `<p class="empty">Nothing awaiting review right now.</p>`}
      </div>

      <div class="card">
        <div class="card__head">
          <h3>All tasks (${list.length})</h3>
          <div style="display:flex;gap:.4rem;flex-wrap:wrap">
            ${chips.map(c => `<button class="mini-btn ${filter === c ? "" : ""}" data-filter="${c}" style="${filter === c ? "background:var(--primary);color:#fff" : ""}">${c}</button>`).join("")}
          </div>
        </div>
        ${list.length ? `<table class="table"><thead><tr><th>Task</th><th>Project</th><th>Labeler</th><th>Reward</th><th>Status</th><th></th></tr></thead><tbody>
          ${list.slice(0, 40).map(t => {
            const lu = t.labelerId ? userById(t.labelerId) : null;
            return `<tr>
              <td style="max-width:240px">${esc(t.question)}</td>
              <td class="muted">${esc(projectName(t.projectId))}</td>
              <td>${lu ? esc(lu.name) : `<select data-assign="${t.id}" aria-label="Assign labeler"><option value="">Assign…</option>${labelers.map(x => `<option value="${x.id}">${esc(x.name)} (${x.skills.join("/")})</option>`).join("")}</select>`}</td>
              <td>${money(t.reward)}</td>
              <td>${UI.badge(t.status)}</td>
              <td class="t-actions">${!lu ? `<button class="mini-btn" data-assign-go="${t.id}">Assign</button>` : ""}</td>
            </tr>`;
          }).join("")}
        </tbody></table>` : `<p class="empty">No tasks match this filter.</p>`}
      </div>`;

    view.querySelectorAll("[data-filter]").forEach(b => b.addEventListener("click", () => { filter = b.dataset.filter; render(); }));
    view.querySelectorAll("[data-approve]").forEach(b => b.addEventListener("click", () => {
      const r = Store.approveTask(b.dataset.approve, user.id);
      const el = view.querySelector(`[data-approve="${b.dataset.approve}"]`);
      if (r.error) { el.closest(".task-row__side").insertAdjacentHTML("beforeend", `<span class="form-status is-error" style="flex-basis:100%">${esc(r.error)}</span>`); }
      else render();
    }));
    view.querySelectorAll("[data-reject]").forEach(b => b.addEventListener("click", () => {
      const row = b.closest(".task-row__side");
      if (row.querySelector("input")) return;
      row.insertAdjacentHTML("beforeend", `<input placeholder="Reason for return…" style="padding:.5rem;border:1px solid var(--line);flex:1" data-reject-note="${b.dataset.reject}" />`);
      const inp = row.querySelector("input");
      inp.focus();
      inp.addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); Store.rejectTask(b.dataset.reject, inp.value); render(); }
      });
      row.insertAdjacentHTML("beforeend", `<button class="mini-btn" data-reject-go="${b.dataset.reject}">Send back</button>`);
      row.querySelector(`[data-reject-go="${b.dataset.reject}"]`).addEventListener("click", () => {
        Store.rejectTask(b.dataset.reject, inp.value); render();
      });
    }));
    view.querySelectorAll("[data-assign-go]").forEach(b => b.addEventListener("click", () => {
      const sel = view.querySelector(`[data-assign="${b.dataset.assignGo}"]`);
      if (!sel || !sel.value) return;
      const d2 = Store.read();
      const t = d2.tasks.find(x => x.id === b.dataset.assignGo);
      t.status = "assigned"; t.labelerId = sel.value; t.assignedAt = new Date().toISOString();
      Store.write(d2);
      Store.notify(sel.value, `New task assigned: ${t.question} (${money(t.reward)}).`, "task");
      render();
    }));
  }

  /* ================= TEAM ================= */
  function team() {
    const d = db();
    const members = o.members.map(id => d.users.find(u => u.id === id)).filter(Boolean);
    const invites = d.invites.filter(i => i.orgId === o.id);
    const requests = (o.requests || []).map(r => ({ ...r, user: d.users.find(u => u.id === r.userId) })).filter(r => r.user);

    view.innerHTML = `
      <div class="grid grid--2">
        <div class="card">
          <div class="card__head"><h3>Members (${members.length})</h3></div>
          <table class="table"><thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead><tbody>
            ${members.map(m => `<tr><td>${esc(m.name)}</td><td class="muted">${esc(m.email)}</td>
              <td>${m.id === o.ownerId ? `<span class="chip">Owner</span>` : `<span class="status status--approved">Member</span>`}</td></tr>`).join("")}
          </tbody></table>

          ${requests.length ? `<h3 style="margin:1.6rem 0 .8rem">Join requests</h3>` + requests.map(r => `
            <div class="task-row"><div class="task-row__main"><strong>${esc(r.user.name)}</strong><span class="muted">${esc(r.user.email)} · ${Store.fmtAgo(r.date)}</span></div>
            <div class="task-row__side">
              <button class="button button--primary button--sm" data-req-approve="${r.userId}">Approve</button>
              <button class="button button--ghost button--sm" data-req-reject="${r.userId}">Decline</button>
            </div></div>`).join("") : ""}
        </div>

        <div class="card">
          <h3 style="margin-bottom:.4rem">Invite by email</h3>
          <p class="form-note" style="margin-bottom:1.2rem">We email the labeler a link like <code>register.html?invite=CODE</code>. (Demo: the invite is created and the link shown below.)</p>
          <form id="invite-form">
            <div class="form-row">
              <div class="field"><label for="inv-email">Email</label><input id="inv-email" type="email" placeholder="teammate@acme.ai" required /></div>
              <div class="field" style="align-self:end"><button class="button button--primary" type="submit">Send invite</button></div>
            </div>
            <p class="form-status" id="invite-status" role="status"></p>
          </form>
          <h3 style="margin:1.4rem 0 .6rem">Pending invites</h3>
          ${invites.length ? invites.map(i => `
            <div class="task-row"><div class="task-row__main"><strong>${esc(i.email)}</strong>
              <span>code <code>${i.code}</code> · ${Store.fmtDate(i.createdAt)}</span></div>
              <div class="task-row__side">${i.status === "pending"
                ? `<a class="mini-btn" href="register.html?invite=${i.code}">Copy invite link</a><span class="status status--pending">pending</span>`
                : `<span class="status status--approved">accepted</span>`}</div>
            </div>`).join("") : `<p class="empty">No invites sent yet.</p>`}
          <hr style="border:0;border-top:1px solid var(--line);margin:1.4rem 0">
          <p class="form-note">Your organization code is <strong>${esc(o.code)}</strong> — share it so people can join from the Register page.</p>
        </div>
      </div>`;

    view.querySelectorAll("[data-req-approve]").forEach(b => b.addEventListener("click", () => {
      const d2 = Store.read();
      const oo = d2.orgs.find(x => x.id === o.id);
      oo.requests = oo.requests.filter(r => r.userId !== b.dataset.reqApprove);
      if (!oo.members.includes(b.dataset.reqApprove)) oo.members.push(b.dataset.reqApprove);
      Store.write(d2);
      Store.notify(b.dataset.reqApprove, `Your request to join ${oo.name} was approved.`, "team");
      render();
    }));
    view.querySelectorAll("[data-req-reject]").forEach(b => b.addEventListener("click", () => {
      const d2 = Store.read();
      const oo = d2.orgs.find(x => x.id === o.id);
      oo.requests = oo.requests.filter(r => r.userId !== b.dataset.reqReject);
      Store.write(d2);
      Store.notify(b.dataset.reqReject, `Your request to join ${oo.name} was declined.`, "team");
      render();
    }));
  }

  /* ---------- unified form handler ---------- */
  function handleForm(e) {
    e.preventDefault();
    const st = e.target.querySelector(".form-status");
    const ok = (msg) => { st.textContent = msg; st.className = "form-status is-ok"; };
    const bad = (msg) => { st.textContent = msg; st.className = "form-status is-error"; };

    if (e.target.id === "upload-form") {
      const name = document.getElementById("ds-name").value.trim();
      const type = document.getElementById("ds-type").value;
      const items = Math.max(1, parseInt(document.getElementById("ds-items").value, 10));
      if (!name) return bad("Name the dataset first.");
      const d = Store.read();
      d.datasets.unshift({ id: Store.uid("d"), orgId: o.id, name, type, items, sizeMB: items * (type === "Video" ? 128 : type === "Audio" ? 12 : 4), uploadedAt: new Date().toISOString() });
      Store.write(d);
      Store.notify(o.ownerId, `Dataset "${name}" (${type}, ${items} items) registered.`, "info");
      ok("Dataset uploaded and registered.");
      setTimeout(render, 700);
    }

    if (e.target.id === "project-form") {
      const title = document.getElementById("pj-title").value.trim();
      const dsId = document.getElementById("pj-dataset").value;
      const reward = Math.max(0.5, parseFloat(document.getElementById("pj-reward").value));
      const count = Math.min(50, Math.max(1, parseInt(document.getElementById("pj-count").value, 10)));
      if (!title || !dsId) return bad("Title and dataset are required.");
      const d = Store.read();
      const ds = d.datasets.find(x => x.id === dsId);
      const proj = { id: Store.uid("p"), orgId: o.id, datasetId: dsId, title, type: ds.type, reward, status: "open", createdAt: new Date().toISOString() };
      d.projects.unshift(proj);
      for (let i = 0; i < count; i++) {
        d.tasks.push({ id: Store.uid("t"), projectId: proj.id, orgId: o.id, reward, status: "available", labelerId: null,
          question: `${ds.type} item ${i + 1} — ${title}`, options: ["Valid", "Invalid", "Needs review"], answer: "", note: "",
          assignedAt: null, submittedAt: null, reviewedAt: null, reviewNote: "" });
      }
      Store.write(d);
      Store.notify(o.ownerId, `Project "${title}" created with ${count} tasks.`, "info");
      ok(`Project created — ${count} tasks generated.`);
      setTimeout(() => document.querySelector('[data-tab="tasks"]').click(), 800);
    }

    if (e.target.id === "invite-form") {
      const email = document.getElementById("inv-email").value.trim().toLowerCase();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return bad("Enter a valid email.");
      const d = Store.read();
      if (d.invites.some(i => i.orgId === o.id && i.email === email && i.status === "pending")) return bad("That email already has a pending invite.");
      const invite = { id: Store.uid("i"), orgId: o.id, email, code: o.code.slice(0, 4) + "-" + Math.random().toString(36).slice(2, 6).toUpperCase(), status: "pending", createdAt: new Date().toISOString() };
      d.invites.unshift(invite);
      Store.write(d);
      const target = d.users.find(u => u.email.toLowerCase() === email);
      if (target) Store.notify(target.id, `${org().name} invited you. Register and redeem code ${invite.code}.`, "team");
      ok(`Invite emailed to ${email} — code ${invite.code}.`);
      setTimeout(render, 900);
    }
  }

  render();
})();
