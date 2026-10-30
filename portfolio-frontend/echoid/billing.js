/* ============ EchoID billing (demo — no real payments) ============ */
(() => {
  if (!ECHO.requireAuth()) return;
  const user = ECHO.currentUser();

  const PLANS = {
    starter: { name: "Starter", price: "$19/mo", amount: 19, hours: 5 },
    growth: { name: "Growth", price: "$79/mo", amount: 79, hours: 50 },
    enterprise: { name: "Enterprise", price: "Custom", amount: 0, hours: Infinity },
  };

  const esc = (s) => { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; };

  /* ---------- current plan + usage ---------- */
  function renderPlan() {
    const p = PLANS[user.plan] || PLANS.growth;
    document.getElementById("planName").textContent = p.name;
    document.getElementById("planPrice").textContent = p.amount ? `$${p.amount} · renews monthly` : "Talk to sales · annual contract";

    const usedMin = Math.round(42 + ECHO.transcripts().reduce((a, t) => a + (t.durationMs || 0), 0) / 60000);
    const cap = p.hours * 60;
    const pct = Number.isFinite(cap) ? Math.min(100, (usedMin / cap) * 100) : 8;
    document.getElementById("usageLabel").textContent = Number.isFinite(cap) ? `${usedMin} / ${cap} min` : `${usedMin} min · unlimited`;
    document.getElementById("usageBar").style.width = pct + "%";

    const files = ECHO.transcripts().length;
    const mb = (18.4 + files * 3.2).toFixed(1);
    const capMb = Number.isFinite(cap) ? cap / 2 : 5000;
    document.getElementById("storageLabel").textContent = `${mb} / ${Math.round(capMb)} MB`;
    document.getElementById("storageBar").style.width = Math.min(100, (mb / capMb) * 100) + "%";
  }

  /* ---------- plan picker ---------- */
  const picker = document.getElementById("planPicker");
  function renderPicker() {
    picker.innerHTML = "";
    for (const [key, p] of Object.entries(PLANS)) {
      const el = document.createElement("div");
      el.className = "plan-pick" + (user.plan === key ? " is-current" : "");
      el.innerHTML = `<h4>${p.name}</h4><p class="p">${p.price}</p>
        <button class="btn ${user.plan === key ? "btn--ghost" : "btn--solid"} btn--sm" ${user.plan === key ? "disabled" : ""}>
          ${user.plan === key ? "Current plan" : "Switch"}</button>`;
      el.querySelector("button").addEventListener("click", () => {
        user.plan = key;
        ECHO.updateAccount(user.email, { plan: key });
        renderPlan(); renderPicker(); renderInvoices();
        ECHO.toast(`Switched to ${p.name}. A demo invoice was generated.`);
      });
      picker.append(el);
    }
  }

  /* ---------- invoices ---------- */
  function renderInvoices() {
    const body = document.getElementById("invoiceRows");
    const p = PLANS[user.plan] || PLANS.growth;
    const now = new Date();
    const rows = [0, 1, 2].map((i) => {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 3);
      return {
        date: d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }),
        plan: p.name,
        amount: p.amount ? `$${p.amount}.00` : "—",
        status: i === 0 ? (p.amount ? "Paid" : "Quote") : "Paid",
      };
    });
    body.innerHTML = rows.map((r, i) => `
      <tr><td>${r.date}</td><td>${r.plan}</td><td>${r.amount}</td>
      <td><span class="badge badge--paid">${r.status}</span></td>
      <td style="text-align:right"><button class="icon-btn" data-i="${i}" title="Download receipt" aria-label="Download receipt">
        <svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg></button></td></tr>`).join("");
    body.querySelectorAll("[data-i]").forEach((b) =>
      b.addEventListener("click", () => {
        const r = rows[+b.dataset.i];
        ECHO.blobDownload(
          `EchoID Labs, Inc.\nReceipt\n\nDate:  ${r.date}\nPlan:  ${r.plan}\nAmount: ${r.amount}\nBilled to: ${user.email}\n\nThank you! (Demo receipt — no real charge was made.)\n`,
          `echoid-receipt-${r.date.replace(/\W+/g, "-")}.txt`, "text/plain");
      })
    );
  }

  /* ---------- payment methods ---------- */
  const K = "echoid.cards";
  const cards = () => { try { return JSON.parse(localStorage.getItem(K)) || []; } catch { return []; } };
  const putCards = (v) => localStorage.setItem(K, JSON.stringify(v));
  if (cards().length === 0) putCards([{ id: crypto.randomUUID(), brand: "VISA", last4: "4242", exp: "08/28", def: true }]);

  const payBox = document.getElementById("payMethods");
  function renderCards() {
    payBox.innerHTML = "";
    for (const c of cards()) {
      const row = document.createElement("div");
      row.className = "pay-method";
      row.innerHTML = `
        <span class="pay-method__icon">${c.brand}</span>
        <span style="flex:1"><b>•••• ${c.last4}</b><small>Expires ${c.exp}${c.def ? " · default" : ""}</small></span>
        <button class="icon-btn icon-btn--del" aria-label="Remove card">
          <svg viewBox="0 0 24 24"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
        </button>`;
      row.querySelector("button").addEventListener("click", () => {
        putCards(cards().filter((x) => x.id !== c.id));
        renderCards();
        ECHO.toast("Payment method removed.");
      });
      payBox.append(row);
    }
    if (!payBox.children.length) payBox.innerHTML = '<p class="empty-note" style="padding:18px">No cards on file.</p>';
  }

  document.getElementById("addCardBtn").addEventListener("click", () => {
    const back = document.createElement("div");
    back.className = "modal-back";
    back.innerHTML = `
      <div class="modal">
        <h3>Add payment method</h3>
        <div class="field"><label>Card number</label><input id="ccNum" inputmode="numeric" placeholder="4242 4242 4242 4242" maxlength="19" /><span class="field__error" data-for="ccNum"></span></div>
        <div style="display:flex;gap:12px">
          <div class="field" style="flex:1"><label>Expiry</label><input id="ccExp" placeholder="MM/YY" maxlength="5" /><span class="field__error" data-for="ccExp"></span></div>
          <div class="field" style="flex:1"><label>CVC</label><input id="ccCvc" inputmode="numeric" placeholder="123" maxlength="4" /><span class="field__error" data-for="ccCvc"></span></div>
        </div>
        <div class="modal__actions">
          <button class="btn btn--ghost btn--sm" data-x="cancel">Cancel</button>
          <button class="btn btn--solid btn--sm" data-x="ok">Save card</button>
        </div>
      </div>`;
    document.body.append(back);
    requestAnimationFrame(() => back.classList.add("is-open"));
    const err = (id, m) => (back.querySelector(`[data-for="${id}"]`).textContent = m);
    back.addEventListener("click", (e) => {
      const close = () => { back.classList.remove("is-open"); setTimeout(() => back.remove(), 250); };
      if (e.target === back || e.target.closest('[data-x="cancel"]')) return close();
      if (e.target.closest('[data-x="ok"]')) {
        const num = back.ccNum.value.replace(/\s+/g, "");
        const exp = back.ccExp.value.trim();
        const cvc = back.ccCvc.value.trim();
        ["ccNum", "ccExp", "ccCvc"].forEach((id) => err(id, ""));
        let ok = true;
        if (!/^\d{13,19}$/.test(num)) { err("ccNum", "Enter a valid card number."); ok = false; }
        if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(exp)) { err("ccExp", "MM/YY"); ok = false; }
        if (!/^\d{3,4}$/.test(cvc)) { err("ccCvc", "3–4 digits"); ok = false; }
        if (!ok) return;
        const list = cards();
        list.push({ id: crypto.randomUUID(), brand: num.startsWith("5") ? "MASTERCARD" : "VISA", last4: num.slice(-4), exp, def: list.length === 0 });
        putCards(list);
        renderCards();
        close();
        ECHO.toast("Card added (demo only — no real payment method was created).");
      }
    });
  });

  renderPlan();
  renderPicker();
  renderInvoices();
  renderCards();
})();
