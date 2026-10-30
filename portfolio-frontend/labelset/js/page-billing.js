/* Labelset — billing: org payments & top-ups, labeler earnings & withdrawals */
(function () {
  "use strict";
  const user = UI.requireUser();
  if (!user) return;
  UI.renderShell("billing");

  const esc = UI.esc, money = UI.money;
  const view = document.getElementById("billing-view");
  const stats = document.getElementById("billing-stats");
  const db = () => Store.read();
  const org = Store.orgOf(user);
  const isOrgView = !!org;

  const stat = (v, l, accent) => `<div class="stat-card"><p class="stat-card__value ${accent ? "stat-card__value--accent" : ""}">${v}</p><p class="stat-card__label">${l}</p></div>`;

  if (isOrgView) renderOrg(); else renderLabeler();

  /* ================= ORGANIZATION ================= */
  function renderOrg() {
    const d = db();
    const pays = d.payments.filter(p => p.orgId === org.id);
    const topups = pays.filter(p => p.type === "topup").reduce((s, p) => s + p.amount, 0);
    const payouts = pays.filter(p => p.type === "payout").reduce((s, p) => s + p.amount, 0);
    const pending = d.tasks.filter(t => t.orgId === org.id && t.status === "submitted").reduce((s, t) => s + t.reward, 0);

    document.getElementById("billing-title").textContent = `${org.name} — billing`;
    stats.innerHTML = `
      ${stat(money(org.balance), "Available balance", true)}
      ${stat(money(topups), "Total added")}
      ${stat(money(payouts), "Paid to labelers")}
      ${stat(money(pending), "Pending verification")}
    `;

    view.innerHTML = `
      <div class="grid grid--2">
        <div class="card">
          <h3 style="margin-bottom:1.1rem">Add funds</h3>
          <p class="form-note" style="margin-bottom:1.2rem">Verified task rewards are deducted from this balance automatically.</p>
          <form id="topup-form">
            <div class="form-row">
              <div class="field"><label for="tu-amount">Amount ($)</label><input id="tu-amount" type="number" min="5" step="5" value="250" required /></div>
              <div class="field"><label for="tu-method">Method</label>
                <select id="tu-method">${org.card ? `<option value="card">Card ····${org.card}</option>` : ""}<option value="demo">Demo payment</option></select></div>
            </div>
            <button class="button button--primary" type="submit">Add funds</button>
            <p class="form-status" id="tu-status" role="status"></p>
          </form>

          <hr style="border:0;border-top:1px solid var(--line);margin:1.6rem 0">
          <h3 style="margin-bottom:1rem">Payment method</h3>
          ${org.card
            ? `<div class="task-row"><div class="task-row__main"><strong>···· ${esc(org.card)}</strong><span>Visa · default card</span></div>
               <div class="task-row__side"><button class="mini-btn" id="remove-card">Remove</button></div></div>`
            : `<form id="card-form">
                 <div class="form-row">
                   <div class="field"><label for="cd-num">Card number</label><input id="cd-num" inputmode="numeric" placeholder="4242 4242 4242 4242" maxlength="19" required /></div>
                   <div class="field"><label for="cd-exp">Expiry</label><input id="cd-exp" placeholder="12/28" required /></div>
                 </div>
                 <button class="button button--ghost button--sm" type="submit">Save card</button>
                 <p class="form-status" id="cd-status" role="status"></p>
               </form>`}
        </div>

        <div class="card">
          <div class="card__head"><h3>Transactions</h3><span class="form-note">top-ups &amp; verified payouts</span></div>
          ${pays.length ? `<table class="table"><thead><tr><th>Description</th><th>Date</th><th>Amount</th></tr></thead><tbody>
            ${pays.map(p => `<tr>
              <td>${esc(p.desc)} <span class="status status--${p.type === "topup" ? "available" : "approved"}" style="margin-left:.4rem">${p.type}</span></td>
              <td class="muted">${Store.fmtDate(p.date)}</td>
              <td class="amount ${p.type === "topup" ? "amount--in" : "amount--out"}">${p.type === "topup" ? "+" : "−"}${money(p.amount)}</td>
            </tr>`).join("")}
          </tbody></table>` : `<p class="empty"><strong>No transactions yet</strong>Add funds to start paying labelers.`}
        </div>
      </div>`;

    document.getElementById("topup-form").addEventListener("submit", e => {
      e.preventDefault();
      const amt = Math.max(5, parseFloat(document.getElementById("tu-amount").value));
      const method = document.getElementById("tu-method").value;
      const d2 = Store.read();
      const oo = d2.orgs.find(x => x.id === org.id);
      oo.balance = +(oo.balance + amt).toFixed(2);
      d2.payments.unshift({ id: Store.uid("pay"), orgId: oo.id, type: "topup", amount: amt, desc: method === "demo" ? "Demo payment" : `Card ····${oo.card}`, date: new Date().toISOString() });
      Store.write(d2);
      Store.notify(oo.ownerId, `${money(amt)} added to ${oo.name}'s balance.`, "money");
      document.getElementById("tu-status").textContent = "Funds added."; document.getElementById("tu-status").className = "form-status is-ok";
      setTimeout(renderOrg, 700);
    });

    const cardForm = document.getElementById("card-form");
    if (cardForm) cardForm.addEventListener("submit", e => {
      e.preventDefault();
      const num = document.getElementById("cd-num").value.replace(/\D/g, "");
      const st = document.getElementById("cd-status");
      if (num.length < 12) { st.textContent = "Enter a valid card number."; st.className = "form-status is-error"; return; }
      const d2 = Store.read();
      d2.orgs.find(x => x.id === org.id).card = num.slice(-4);
      Store.write(d2);
      renderOrg();
    });
    const rc = document.getElementById("remove-card");
    if (rc) rc.addEventListener("click", () => {
      const d2 = Store.read();
      d2.orgs.find(x => x.id === org.id).card = null;
      Store.write(d2);
      renderOrg();
    });
  }

  /* ================= LABELER ================= */
  function renderLabeler() {
    const d = db();
    const mine = d.tasks.filter(t => t.labelerId === user.id);
    const approved = mine.filter(t => t.status === "approved");
    const earned = approved.reduce((s, t) => s + t.reward, 0);
    const pendingReview = mine.filter(t => t.status === "submitted").reduce((s, t) => s + t.reward, 0);
    const wds = d.withdrawals.filter(w => w.userId === user.id);
    const withdrawn = wds.filter(w => w.status !== "cancelled").reduce((s, w) => s + w.amount, 0);

    document.getElementById("billing-title").textContent = "Earnings & payouts";
    stats.innerHTML = `
      ${stat(money(user.balance || 0), "Available balance", true)}
      ${stat(money(earned), "Verified earnings")}
      ${stat(money(pendingReview), "Pending verification")}
      ${stat(money(withdrawn), "Withdrawn to date")}
    `;

    view.innerHTML = `
      <div class="grid grid--2">
        <div class="card">
          <h3 style="margin-bottom:1.1rem">Withdraw funds</h3>
          <p class="form-note" style="margin-bottom:1.2rem">Only <strong>verified</strong> task rewards can be withdrawn. Minimum ${money(5)}.</p>
          <form id="wd-form">
            <div class="form-row">
              <div class="field"><label for="wd-amount">Amount ($)</label><input id="wd-amount" type="number" min="5" step="0.5" required /></div>
              <div class="field"><label for="wd-method">Method</label><select id="wd-method"><option>Bank transfer</option><option>PayPal</option><option>Mobile money</option></select></div>
            </div>
            <button class="button button--primary" type="submit" ${user.balance >= 5 ? "" : "disabled"}>Request withdrawal</button>
            <p class="form-status" id="wd-status" role="status"></p>
          </form>

          <hr style="border:0;border-top:1px solid var(--line);margin:1.6rem 0">
          <h3 style="margin-bottom:1rem">Withdrawal history</h3>
          ${wds.length ? wds.map(w => `<div class="task-row">
            <div class="task-row__main"><strong>${money(w.amount)}</strong><span>${Store.fmtDate(w.date)}</span></div>
            <div class="task-row__side">${UI.badge(w.status)}</div>
          </div>`).join("") : `<p class="empty"><strong>No withdrawals yet</strong>Your payout requests will show here.</p>`}
        </div>

        <div class="card">
          <div class="card__head"><h3>Earnings by task</h3><span class="form-note">released on verification</span></div>
          ${approved.length ? `<table class="table"><thead><tr><th>Task</th><th>Organization</th><th>Verified</th><th>Amount</th></tr></thead><tbody>
            ${approved.map(t => `<tr>
              <td style="max-width:240px">${esc(t.question)}</td>
              <td class="muted">${esc((d.orgs.find(x => x.id === t.orgId) || {}).name || "—")}</td>
              <td class="muted">${t.reviewedAt ? Store.fmtDate(t.reviewedAt) : "—"}</td>
              <td class="amount amount--in">+${money(t.reward)}</td>
            </tr>`).join("")}
          </tbody></table>` : `<p class="empty"><strong>No verified earnings yet</strong>Submit tasks and wait for the organization to verify them.</p>`}
          ${pendingReview > 0 ? `<p class="form-note" style="margin-top:1rem">${money(pendingReview)} is waiting for verification across ${mine.filter(t => t.status === "submitted").length} task(s).</p>` : ""}
        </div>
      </div>`;

    document.getElementById("wd-form").addEventListener("submit", e => {
      e.preventDefault();
      const amt = parseFloat(document.getElementById("wd-amount").value);
      const st = document.getElementById("wd-status");
      const d2 = Store.read();
      const u = d2.users.find(x => x.id === user.id);
      if (!(amt >= 5)) { st.textContent = "Minimum withdrawal is $5.00."; st.className = "form-status is-error"; return; }
      if (amt > u.balance) { st.textContent = `You can withdraw up to ${money(u.balance)}.`; st.className = "form-status is-error"; return; }
      u.balance = +(u.balance - amt).toFixed(2);
      d2.withdrawals.unshift({ id: Store.uid("w"), userId: u.id, amount: amt, status: "pending", date: new Date().toISOString() });
      Store.write(d2);
      Store.notify(u.id, `Withdrawal of ${money(amt)} requested — processing in 1–2 business days.`, "money");
      st.textContent = "Withdrawal requested."; st.className = "form-status is-ok";
      setTimeout(renderLabeler, 800);
    });
  }
})();
