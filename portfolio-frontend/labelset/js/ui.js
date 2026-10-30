/* Labelset — shared app shell: header, search, notifications, auth guards */
(function () {
  "use strict";

  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function initials(name) {
    return name.split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
  }

  /* ---------- header ---------- */
  function renderShell(active) {
    const user = Store.me();
    const header = document.getElementById("app-header");
    if (!header) return;
    if (!user) {
      header.innerHTML = `
        <div class="shell container">
          <a class="shell__logo" href="index.html">${logoSvg()}<span>Labelset</span></a>
          <div class="shell__actions">
            <a class="button button--text" href="register.html#login">Log in</a>
            <a class="button button--primary" href="register.html">Get Started</a>
          </div>
        </div>`;
      return;
    }

    const org = Store.orgOf(user);
    const isOrg = !!Store.ownedOrg(user) || (!!org && org.ownerId !== user.id);
    const links = isOrg
      ? [["dashboard-org.html", "Org Dashboard", "org"], ["billing.html", "Billing", "billing"]]
      : [["dashboard-labeler.html", "My Tasks", "labeler"], ["billing.html", "Earnings", "billing"]];

    header.classList.add("app-header");
    header.innerHTML = `
      <div class="shell container">
        <a class="shell__logo" href="index.html">${logoSvg()}<span>Labelset</span></a>
        <nav class="shell__nav">
          ${links.map(([href, label, key]) => `<a href="${href}" class="shell__link ${active === key ? "is-active" : ""}">${label}</a>`).join("")}
        </nav>
        <div class="shell__search" id="global-search">
          <input type="search" id="search-input" placeholder="Search people & organizations…" autocomplete="off" aria-label="Search users and organizations" />
          <div class="search-pop" id="search-pop" hidden></div>
        </div>
        <div class="shell__actions">
          <button class="icon-btn" id="bell-btn" aria-label="Notifications">
            ${bellSvg()}<span class="badge" id="bell-count" hidden></span>
          </button>
          <div class="user-menu" id="user-menu">
            <button class="avatar" id="avatar-btn" aria-label="Account menu">${esc(initials(user.name))}</button>
            <div class="user-pop" id="user-pop" hidden>
              <div class="user-pop__head">
                <strong>${esc(user.name)}</strong>
                <span>${esc(user.email)}</span>
                <span class="chip">${org ? (org.ownerId === user.id ? "Org owner" : "Org member") : "Labeler"}</span>
              </div>
              <button id="logout-btn" class="user-pop__logout">Log out</button>
            </div>
          </div>
        </div>
      </div>
      <div class="notif-panel" id="notif-panel" hidden></div>`;

    bindSearch();
    bindNotifications();
    document.getElementById("logout-btn").addEventListener("click", () => {
      Store.logout();
      location.href = "index.html";
    });
    const avatarBtn = document.getElementById("avatar-btn");
    const userPop = document.getElementById("user-pop");
    avatarBtn.addEventListener("click", e => { e.stopPropagation(); userPop.hidden = !userPop.hidden; });
    document.addEventListener("click", e => {
      if (!e.target.closest(".user-menu")) userPop.hidden = true;
      if (!e.target.closest(".shell__search")) document.getElementById("search-pop").hidden = true;
      if (!e.target.closest("#bell-btn") && !e.target.closest(".notif-panel")) document.getElementById("notif-panel").hidden = true;
    });
  }

  function logoSvg() {
    return `<svg viewBox="0 0 24 24" class="logo-mark" aria-hidden="true"><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5v-9Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="12" cy="12" r="2.6" fill="currentColor"/></svg>`;
  }
  function bellSvg() {
    return `<svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 22a2.2 2.2 0 0 0 2.2-2.2H9.8A2.2 2.2 0 0 0 12 22Zm7-5.4-1.6-1.9v-4A5.5 5.5 0 0 0 13 5.2V4a1 1 0 0 0-2 0v1.2a5.5 5.5 0 0 0-4.4 5.5v4L5 16.6a1 1 0 0 0 .8 1.6h11.4a1 1 0 0 0 .8-1.6Z" fill="currentColor"/></svg>`;
  }

  /* ---------- notifications ---------- */
  function bindNotifications() {
    const btn = document.getElementById("bell-btn");
    const panel = document.getElementById("notif-panel");
    const user = Store.me();
    const db = Store.read();
    const mine = db.notifications.filter(n => n.userId === user.id);
    const unread = mine.filter(n => !n.read).length;
    const count = document.getElementById("bell-count");
    count.hidden = !unread;
    count.textContent = unread;

    panel.innerHTML = `
      <div class="notif-panel__head">
        <strong>Notifications</strong>
        <button id="mark-read" ${unread ? "" : "disabled"}>Mark all read</button>
      </div>
      ${mine.length ? mine.slice(0, 12).map(n => `
        <div class="notif ${n.read ? "" : "is-unread"}">
          <span class="notif__dot notif__dot--${n.type}"></span>
          <div><p>${esc(n.text)}</p><time>${Store.fmtAgo(n.date)}</time></div>
        </div>`).join("") : `<p class="notif-empty">You're all caught up.</p>`}`;

    btn.addEventListener("click", e => { e.stopPropagation(); panel.hidden = !panel.hidden; });
    panel.addEventListener("click", e => e.stopPropagation());
    document.getElementById("mark-read").addEventListener("click", () => {
      const db2 = Store.read();
      db2.notifications.forEach(n => { if (n.userId === user.id) n.read = true; });
      Store.write(db2);
      bindNotifications();
    });
  }

  /* ---------- global search (users + orgs) ---------- */
  function bindSearch() {
    const input = document.getElementById("search-input");
    const pop = document.getElementById("search-pop");
    const user = Store.me();
    const myOrg = Store.ownedOrg(user);

    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      if (q.length < 2) { pop.hidden = true; return; }
      const db = Store.read();
      const users = db.users.filter(u => u.id !== user.id && (u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))).slice(0, 5);
      const orgs = db.orgs.filter(o => o.name.toLowerCase().includes(q)).slice(0, 5);

      pop.innerHTML = (!users.length && !orgs.length)
        ? `<p class="search-pop__empty">No matches for “${esc(q)}”.</p>`
        : [
            orgs.length ? `<p class="search-pop__group">Organizations</p>` + orgs.map(o => `
              <div class="search-pop__row">
                <div><strong>${esc(o.name)}</strong><span>${esc(o.industry || "AI data")}${myOrg && myOrg.id === o.id ? " · your org" : ""}</span></div>
                ${myOrg && myOrg.id === o.id ? "" : `<button class="mini-btn" data-join="${o.id}">Request access</button>`}
              </div>`).join("") : "",
            users.length ? `<p class="search-pop__group">People</p>` + users.map(u => `
              <div class="search-pop__row">
                <div><strong>${esc(u.name)}</strong><span>${esc(u.email)} · ${esc((u.skills || []).join(", ") || "Labeler")}</span></div>
                ${myOrg ? `<button class="mini-btn" data-invite="${esc(u.email)}">Invite</button>` : ""}
              </div>`).join("") : ""
          ].join("");
      pop.hidden = false;

      pop.querySelectorAll("[data-join]").forEach(b => b.addEventListener("click", () => {
        const db2 = Store.read();
        const o = db2.orgs.find(x => x.id === b.dataset.join);
        o.requests = o.requests || [];
        if (!o.requests.some(r => r.userId === user.id) && !o.members.includes(user.id)) {
          o.requests.push({ userId: user.id, date: new Date().toISOString() });
          Store.write(db2);
          Store.notify(o.ownerId, `${user.name} requested to join ${o.name}.`, "team");
          b.outerHTML = `<span class="mini-btn is-done">Requested</span>`;
        } else {
          b.outerHTML = `<span class="mini-btn is-done">Already pending/member</span>`;
        }
      }));
      pop.querySelectorAll("[data-invite]").forEach(b => b.addEventListener("click", () => {
        const db2 = Store.read();
        const email = b.dataset.invite;
        if (!db2.invites.some(i => i.orgId === myOrg.id && i.email === email && i.status === "pending")) {
          db2.invites.unshift({ id: Store.uid("i"), orgId: myOrg.id, email, code: myOrg.code.slice(0, 4) + "-" + Math.random().toString(36).slice(2, 6).toUpperCase(), status: "pending", createdAt: new Date().toISOString() });
          Store.write(db2);
          const target = db2.users.find(u => u.email === email);
          if (target) Store.notify(target.id, `You were invited to join ${myOrg.name}. Open Register → Join with code.`, "team");
          b.outerHTML = `<span class="mini-btn is-done">Invite sent</span>`;
        } else {
          b.outerHTML = `<span class="mini-btn is-done">Already invited</span>`;
        }
      }));
    });
    input.addEventListener("click", () => { if (input.value.trim().length >= 2) pop.hidden = false; });
  }

  /* ---------- guards ---------- */
  function requireUser(redirect = "register.html#login") {
    if (!Store.me()) { location.href = redirect; return null; }
    return Store.me();
  }
  function requireOrg(redirect = "dashboard-labeler.html") {
    const u = requireUser();
    if (!u) return null;
    const org = Store.orgOf(u);
    if (!org) { location.href = redirect; return null; }
    return { user: u, org };
  }
  function requireLabeler(redirect = "dashboard-org.html") {
    const u = requireUser();
    if (!u) return null;
    if (Store.orgOf(u)) { location.href = redirect; return null; }
    return u;
  }

  /* ---------- misc helpers ---------- */
  const badge = status => `<span class="status status--${status}">${status}</span>`;

  function tabs(root, onChange) {
    root.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
      root.querySelectorAll(".tab").forEach(x => x.classList.remove("is-active"));
      t.classList.add("is-active");
      onChange(t.dataset.tab);
    }));
  }

  window.UI = { renderShell, requireUser, requireOrg, requireLabeler, esc, initials, badge, tabs, money: Store.money };
})();
