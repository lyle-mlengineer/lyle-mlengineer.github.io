const PACKS = {
  p100: { credits: 100, price: 9 },
  p500: { credits: 500, price: 39 },
  p1200: { credits: 1200, price: 79 },
  p3000: { credits: 3000, price: 179 },
};

const PLANS = {
  starter: { name: "Starter", price: 0, meta: "20 faces / month" },
  creator: { name: "Creator", price: 29, meta: "500 faces / month" },
  studio: { name: "Studio", price: 149, meta: "5,000 faces / month" },
};

const packButtons = document.querySelectorAll("[data-pack]");
const planButtons = document.querySelectorAll("[data-plan]");
const summaryTitle = document.getElementById("summaryTitle");
const summaryNote = document.getElementById("summaryNote");
const summaryPrice = document.getElementById("summaryPrice");
const summarySubtotal = document.getElementById("summarySubtotal");
const summaryTax = document.getElementById("summaryTax");
const summaryTotal = document.getElementById("summaryTotal");
const payBtn = document.getElementById("payBtn");
const checkoutForm = document.getElementById("checkoutForm");
const checkoutView = document.getElementById("checkoutView");
const checkoutSuccess = document.getElementById("checkoutSuccess");
const successTitle = document.getElementById("successTitle");
const successCopy = document.getElementById("successCopy");
const terms = document.getElementById("terms");
const newCardFields = document.getElementById("newCardFields");
const pmSaved = document.getElementById("pmSaved");
const pmNew = document.getElementById("pmNew");

let selection = { type: "pack", id: "p500" };
let paying = false;

const queryPlan = new URLSearchParams(location.search).get("plan");
if (queryPlan && PLANS[queryPlan]) selection = { type: "plan", id: queryPlan };

function selectionData() {
  if (selection.type === "pack") {
    const pack = PACKS[selection.id];
    return {
      title: `${FF.num(pack.credits)} credits`,
      note: "One-time purchase · never expires",
      price: pack.price,
      monthly: false,
    };
  }
  const plan = PLANS[selection.id];
  return {
    title: `${plan.name} plan`,
    note: `${plan.meta} · billed monthly`,
    price: plan.price,
    monthly: true,
  };
}

function totals() {
  const { price } = selectionData();
  const tax = Math.round(price * 0.08 * 100) / 100;
  return { subtotal: price, tax, total: Math.round((price + tax) * 100) / 100 };
}

function syncPlanTags() {
  const plan = FF.getPlan();
  planButtons.forEach((btn) => {
    const tag = btn.querySelector(".pc-current");
    if (tag) tag.hidden = btn.dataset.plan !== plan;
  });
}

function renderSummary() {
  const item = selectionData();
  const sums = totals();

  packButtons.forEach((btn) => {
    btn.setAttribute("aria-pressed", String(selection.type === "pack" && btn.dataset.pack === selection.id));
  });
  planButtons.forEach((btn) => {
    btn.setAttribute("aria-pressed", String(selection.type === "plan" && btn.dataset.plan === selection.id));
  });

  summaryTitle.textContent = item.title;
  summaryNote.textContent = item.note;
  summaryPrice.textContent = `$${item.price.toFixed(2)}`;
  summarySubtotal.textContent = `$${sums.subtotal.toFixed(2)}`;
  summaryTax.textContent = `$${sums.tax.toFixed(2)}`;
  summaryTotal.textContent = `$${sums.total.toFixed(2)}`;

  const isCurrentPlan = selection.type === "plan" && selection.id === FF.getPlan();

  if (isCurrentPlan) {
    payBtn.textContent = "Current plan";
  } else if (sums.total === 0) {
    payBtn.textContent = "Switch to Starter";
  } else {
    payBtn.textContent = `Pay $${sums.total.toFixed(2)}`;
  }
  payBtn.disabled = isCurrentPlan;

  syncPlanTags();
}

function syncBalance() {
  document.querySelectorAll("[data-credits]").forEach((el) => {
    el.textContent = FF.num(FF.getCredits());
  });
  document.querySelectorAll("[data-plan-label]").forEach((el) => {
    const plan = PLANS[FF.getPlan()] || PLANS.creator;
    el.textContent = `${plan.name} plan`;
  });
}

function addInvoice(label, amount) {
  const row = document.createElement("div");
  row.className = "invoice-row";

  const copy = document.createElement("span");
  const strong = document.createElement("strong");
  strong.textContent = label;
  const date = document.createElement("span");
  date.textContent = " · Oct 30, 2026";
  copy.append(strong, date);

  const amountEl = document.createElement("span");
  amountEl.className = "inv-amount";
  amountEl.textContent = `$${amount.toFixed(2)}`;

  const status = document.createElement("span");
  status.className = "inv-status";
  status.textContent = "Paid";

  const receipt = document.createElement("button");
  receipt.type = "button";
  receipt.className = "inv-link";
  receipt.setAttribute("data-receipt", "");
  receipt.textContent = "Receipt";

  row.append(copy, amountEl, status, receipt);
  document.getElementById("invoiceList").prepend(row);
}

packButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    selection = { type: "pack", id: btn.dataset.pack };
    renderSummary();
  });
});

planButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    selection = { type: "plan", id: btn.dataset.plan };
    renderSummary();
  });
});

function setPaymentMethod(method) {
  const isNew = method === "new";
  pmSaved.classList.toggle("is-active", !isNew);
  pmNew.classList.toggle("is-active", isNew);
  pmSaved.setAttribute("aria-pressed", String(!isNew));
  pmNew.setAttribute("aria-pressed", String(isNew));
  newCardFields.classList.toggle("is-hidden", !isNew);

  newCardFields.querySelectorAll("input").forEach((input) => {
    input.required = isNew;
  });

  if (isNew) document.getElementById("cardName").focus();
}

pmSaved.addEventListener("click", () => setPaymentMethod("saved"));
pmNew.addEventListener("click", () => setPaymentMethod("new"));

// Light formatting for the card fields
const cardNumber = document.getElementById("cardNumber");
const cardExpiry = document.getElementById("cardExpiry");
const cardCvc = document.getElementById("cardCvc");

cardNumber.addEventListener("input", () => {
  const digits = cardNumber.value.replace(/\D/g, "").slice(0, 16);
  cardNumber.value = digits.replace(/(\d{4})(?=\d)/g, "$1 ");
});

cardExpiry.addEventListener("input", () => {
  const digits = cardExpiry.value.replace(/\D/g, "").slice(0, 4);
  cardExpiry.value = digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
});

cardCvc.addEventListener("input", () => {
  cardCvc.value = cardCvc.value.replace(/\D/g, "").slice(0, 4);
});

checkoutForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (paying) return;

  if (!terms.checked) {
    FF.toast("Please accept the terms of sale first");
    terms.focus();
    return;
  }

  if (pmNew.getAttribute("aria-pressed") === "true") {
    const required = [cardNumber, cardExpiry, cardCvc].filter((input) => !input.value.trim());
    if (required.length) {
      FF.toast("Add your card details to continue");
      required[0].focus();
      return;
    }
  }

  paying = true;
  const original = payBtn.textContent;
  payBtn.disabled = true;
  payBtn.textContent = "Processing…";

  setTimeout(() => {
    const item = selectionData();
    const sums = totals();

    addInvoice(item.title, sums.total);
    syncBalance();

    if (selection.type === "pack") {
      const pack = PACKS[selection.id];
      FF.setCredits(FF.getCredits() + pack.credits);
      successTitle.textContent = "Payment complete";
      successCopy.textContent = `${FF.num(pack.credits)} credits were added to your workspace.`;
      FF.toast(`${FF.num(pack.credits)} credits added`);
    } else {
      const plan = PLANS[selection.id];
      FF.setPlan(selection.id);
      successTitle.textContent = "Plan updated";
      successCopy.textContent = `You're now on the ${plan.name} plan — ${plan.meta}.`;
      FF.toast(`Switched to the ${plan.name} plan`);
    }

    syncBalance();
    syncPlanTags();
    checkoutView.hidden = true;
    checkoutSuccess.hidden = false;

    paying = false;
    payBtn.disabled = false;
    payBtn.textContent = original;
  }, 900);
});

document.getElementById("buyAgain").addEventListener("click", () => {
  checkoutSuccess.hidden = true;
  checkoutView.hidden = false;
  terms.checked = false;
  selection = { type: "pack", id: "p500" };
  renderSummary();
  document.getElementById("packs").scrollIntoView({ behavior: "smooth", block: "start" });
});

document.getElementById("invoiceList").addEventListener("click", (event) => {
  if (event.target.closest("[data-receipt]")) {
    FF.toast("Receipt sent to ada@studio.com");
  }
});

syncBalance();
renderSummary();
