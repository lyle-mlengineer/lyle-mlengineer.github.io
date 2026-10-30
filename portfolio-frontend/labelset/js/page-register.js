/* Labelset — register / login / join flows */
(function () {
  "use strict";
  const $ = s => document.querySelector(s);
  const esc = UI.esc;
  UI.renderShell();

  /* already logged in? send to the right dashboard (unless joining with a code) */
  if (Store.me() && location.hash !== "#join") location.href = Store.ownedOrg(Store.me()) ? "dashboard-org.html" : "dashboard-labeler.html";

  /* ---------- tabs ---------- */
  const tabs = document.querySelectorAll(".auth-tabs button");
  const panes = { login: $("#pane-login"), register: $("#pane-register"), join: $("#pane-join") };
  function show(name) {
    tabs.forEach(t => t.classList.toggle("is-active", t.dataset.pane === name));
    Object.entries(panes).forEach(([k, el]) => (el.hidden = k !== name));
  }
  tabs.forEach(t => t.addEventListener("click", () => show(t.dataset.pane)));

  /* ---------- invite link (?invite=CODE) ---------- */
  const inviteCode = new URLSearchParams(location.search).get("invite");
  const pendingKey = "labelset_pending_invite";
  if (inviteCode) {
    sessionStorage.setItem(pendingKey, inviteCode);
    const banner = $("#invite-banner");
    const org = Store.read().orgs.find(o => Store.read().invites.some(i => i.code === inviteCode && i.orgId === o.id));
    banner.hidden = false;
    banner.innerHTML = `You've been invited${org ? ` to join <strong>${esc(org.name)}</strong>` : ""}. Register below and redeem your code with the email the invite was sent to.`;
    show("register");
  } else if (location.hash === "#join") show("join");
  else if (location.hash === "#register") show("register");

  /* ---------- login ---------- */
  function afterLogin(user) {
    const code = sessionStorage.getItem(pendingKey);
    if (code) tryRedeem(user, code, () => {});
    location.href = Store.ownedOrg(user) || Store.orgOf(user) ? "dashboard-org.html" : "dashboard-labeler.html";
  }

  $("#pane-login").addEventListener("submit", e => {
    e.preventDefault();
    const st = $("#login-status");
    const u = Store.login($("#l-email").value, $("#l-pass").value);
    if (!u) { st.textContent = "Wrong email or password. Try a demo account below."; st.className = "form-status is-error"; return; }
    st.textContent = "Welcome back!"; st.className = "form-status is-ok";
    setTimeout(() => afterLogin(u), 250);
  });
  document.querySelectorAll("[data-demo]").forEach(b => b.addEventListener("click", () => {
    $("#l-email").value = b.dataset.demo;
    $("#l-pass").value = "demo1234";
    $("#pane-login").dispatchEvent(new Event("submit", { cancelable: true }));
  }));

  /* ---------- register ---------- */
  document.querySelectorAll('input[name="r-kind"]').forEach(r => r.addEventListener("change", () => {
    const isOrg = $("#r-org").checked;
    $("#org-name-field").hidden = !isOrg;
    $("#skills-field").hidden = isOrg;
  }));

  $("#pane-register").addEventListener("submit", e => {
    e.preventDefault();
    const st = $("#register-status");
    const name = $("#r-name").value.trim();
    const email = $("#r-email").value.trim().toLowerCase();
    const pass = $("#r-pass").value;
    const isOrg = $("#r-org").checked;
    const db = Store.read();

    if (name.length < 2) return fail("Please enter your full name.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return fail("That email doesn't look right.");
    if (pass.length < 8) return fail("Password needs at least 8 characters.");
    if (db.users.some(u => u.email.toLowerCase() === email)) return fail("An account with this email already exists — log in instead.");
    if (isOrg && $("#r-orgname").value.trim().length < 2) return fail("Give your organization a name.");

    const user = {
      id: Store.uid("u"), name, email, password: pass,
      kind: "labeler",
      skills: isOrg ? [] : [...document.querySelectorAll(".skill:checked")].map(c => c.value),
      balance: 0, joined: new Date().toISOString()
    };
    db.users.push(user);

    if (isOrg) {
      const org = {
        id: Store.uid("o"), name: $("#r-orgname").value.trim(),
        industry: "AI data", ownerId: user.id,
        code: user.name.split(" ")[0].slice(0, 4).toUpperCase() + "-" + Math.random().toString(36).slice(2, 6).toUpperCase(),
        balance: 0, card: null, members: [user.id], requests: [], createdAt: new Date().toISOString()
      };
      db.orgs.push(org);
      Store.notify(user.id, `Welcome! Your org code is ${org.code} — share it to invite teammates.`, "team");
    } else {
      Store.notify(user.id, "Welcome to Labelset! Accept your first task from My Tasks.", "info");
    }
    Store.write(db);
    Store.setSession(user.id);

    const code = sessionStorage.getItem(pendingKey);
    if (code) tryRedeem(user, code, () => {});
    st.textContent = "Account created! Redirecting…"; st.className = "form-status is-ok";
    setTimeout(() => { location.href = isOrg ? "dashboard-org.html" : "dashboard-labeler.html"; }, 400);

    function fail(msg) { st.textContent = msg; st.className = "form-status is-error"; }
  });

  /* ---------- join with code / request access ---------- */
  function tryRedeem(user, code, done) {
    const db = Store.read();
    const invite = db.invites.find(i => i.code.toUpperCase() === code.toUpperCase() && i.status === "pending");
    if (!invite) { done(false, "Invite code not found or already used."); return; }
    if (invite.email.toLowerCase() !== user.email.toLowerCase()) {
      done(false, `This invite was sent to ${invite.email}. Log in with that email.`); return;
    }
    const org = db.orgs.find(o => o.id === invite.orgId);
    invite.status = "accepted";
    if (!org.members.includes(user.id)) org.members.push(user.id);
    Store.write(db);
    Store.notify(org.ownerId, `${user.name} joined ${org.name} via invite.`, "team");
    sessionStorage.removeItem(pendingKey);
    done(true, `You joined ${org.name}!`);
  }

  $("#pane-join").addEventListener("submit", e => {
    e.preventDefault();
    const st = $("#join-status");
    const user = Store.me();
    if (!user) { st.textContent = "Please log in first."; st.className = "form-status is-error"; show("login"); return; }
    const code = $("#j-code").value.trim();
    if (!code) { st.textContent = "Enter an invite code."; st.className = "form-status is-error"; return; }
    tryRedeem(user, code, (ok, msg) => {
      st.textContent = msg; st.className = "form-status " + (ok ? "is-ok" : "is-error");
      if (ok) setTimeout(() => (location.href = "dashboard-org.html"), 700);
    });
  });

  $("#j-search").addEventListener("input", () => {
    const q = $("#j-search").value.trim().toLowerCase();
    const box = $("#j-results");
    if (q.length < 2) { box.innerHTML = ""; return; }
    const db = Store.read();
    const me = Store.me();
    const orgs = db.orgs.filter(o => o.name.toLowerCase().includes(q));
    box.innerHTML = orgs.length ? orgs.map(o => {
      const member = me && o.members.includes(me.id);
      const pending = me && (o.requests || []).some(r => r.userId === me.id);
      return `<div class="search-pop__row" style="border:1px solid var(--line);margin-bottom:.6rem">
        <div><strong>${esc(o.name)}</strong><span>${esc(o.industry)}</span></div>
        ${member ? `<span class="mini-btn is-done">Member</span>`
          : pending ? `<span class="mini-btn is-done">Pending</span>`
          : `<button class="mini-btn" data-req="${o.id}">Request access</button>`}
      </div>`;
    }).join("") : `<p class="form-note">No organizations match.</p>`;

    box.querySelectorAll("[data-req]").forEach(b => b.addEventListener("click", () => {
      const user = Store.me();
      if (!user) { show("login"); $("#join-status").textContent = "Log in first, then request access."; $("#join-status").className = "form-status is-error"; return; }
      const db2 = Store.read();
      const o = db2.orgs.find(x => x.id === b.dataset.req);
      o.requests = o.requests || [];
      o.requests.push({ userId: user.id, date: new Date().toISOString() });
      Store.write(db2);
      Store.notify(o.ownerId, `${user.name} requested to join ${o.name}.`, "team");
      b.outerHTML = `<span class="mini-btn is-done">Requested ✓</span>`;
    }));
  });
})();
