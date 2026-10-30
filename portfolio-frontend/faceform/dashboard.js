// ---------- Usage chart ----------
const USAGE = {
  "7d": {
    total: "684K",
    delta: "+4.1%",
    requests: "9,140 API calls",
    labels: ["Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed"],
    points: [
      { img: 74, prompt: 13 },
      { img: 88, prompt: 16 },
      { img: 61, prompt: 11 },
      { img: 55, prompt: 10 },
      { img: 96, prompt: 18 },
      { img: 103, prompt: 19 },
      { img: 79, prompt: 14 },
    ],
  },
  "30d": {
    total: "2.84M",
    delta: "+6.2%",
    requests: "38.6K API calls",
    labels: ["Oct 1", "Oct 4", "Oct 7", "Oct 10", "Oct 13", "Oct 16", "Oct 19", "Oct 22", "Oct 25", "Oct 28"],
    points: [
      { img: 68, prompt: 12 },
      { img: 82, prompt: 15 },
      { img: 74, prompt: 13 },
      { img: 91, prompt: 17 },
      { img: 86, prompt: 15 },
      { img: 104, prompt: 19 },
      { img: 97, prompt: 17 },
      { img: 112, prompt: 20 },
      { img: 121, prompt: 22 },
      { img: 96, prompt: 17 },
    ],
  },
  "90d": {
    total: "8.12M",
    delta: "+11.8%",
    requests: "112K API calls",
    labels: ["Aug 4", "Aug 11", "Aug 18", "Aug 25", "Sep 1", "Sep 8", "Sep 15", "Sep 22", "Sep 29", "Oct 6", "Oct 13", "Oct 20", "Oct 27"],
    points: [
      { img: 72, prompt: 13 },
      { img: 78, prompt: 14 },
      { img: 69, prompt: 12 },
      { img: 84, prompt: 15 },
      { img: 91, prompt: 16 },
      { img: 87, prompt: 16 },
      { img: 98, prompt: 18 },
      { img: 94, prompt: 17 },
      { img: 106, prompt: 19 },
      { img: 115, prompt: 21 },
      { img: 109, prompt: 20 },
      { img: 124, prompt: 23 },
      { img: 118, prompt: 21 },
    ],
  },
};

const usageChart = document.getElementById("usageChart");
const usageTotal = document.getElementById("usageTotal");
const usageDelta = document.getElementById("usageDelta");
const usageRequests = document.getElementById("usageRequests");
const rangeButtons = document.querySelectorAll("#usageRange .seg");

function renderUsage(range) {
  const data = USAGE[range];
  const max = Math.max(...data.points.map((p) => p.img + p.prompt));
  const labelEvery = Math.ceil(data.points.length / 7);

  usageChart.replaceChildren();

  data.points.forEach((point, index) => {
    const col = document.createElement("div");
    col.className = "chart-col";
    col.title = `${data.labels[index]}: ${Math.round((point.img + point.prompt) * 1000).toLocaleString("en-US")} tokens`;

    const stack = document.createElement("div");
    stack.className = "bar-stack";

    const img = document.createElement("span");
    img.className = "bar bar-img";
    img.style.height = `${(point.img / max) * 100}%`;

    const prompt = document.createElement("span");
    prompt.className = "bar bar-prompt";
    prompt.style.height = `${(point.prompt / max) * 100}%`;

    stack.append(prompt, img);

    if (index % labelEvery === 0) {
      const label = document.createElement("span");
      label.className = "chart-x";
      label.textContent = data.labels[index];
      stack.append(label);
    }

    col.append(stack);
    usageChart.append(col);
  });

  usageTotal.textContent = data.total;
  usageDelta.textContent = data.delta;
  usageRequests.textContent = data.requests;
  usageChart.setAttribute(
    "aria-label",
    `Token usage for the selected period: ${data.total} tokens across ${data.requests}.`
  );

  rangeButtons.forEach((btn) => {
    btn.setAttribute("aria-pressed", String(btn.dataset.range === range));
  });
}

rangeButtons.forEach((btn) => {
  btn.addEventListener("click", () => renderUsage(btn.dataset.range));
});

renderUsage("7d");

// ---------- Credits & plan ----------
const PLAN_NAMES = { starter: "Starter", creator: "Creator", studio: "Studio" };
const PLAN_CREDITS = { starter: 500, creator: 5000, studio: 50000 };

function syncAccount() {
  const credits = FF.getCredits();
  const plan = FF.getPlan();
  const max = PLAN_CREDITS[plan] || 5000;
  const pct = Math.min(100, Math.round((credits / max) * 100));

  document.querySelectorAll("[data-credits]").forEach((el) => {
    el.textContent = FF.num(credits);
  });
  document.querySelectorAll("[data-credit-total]").forEach((el) => {
    el.textContent = FF.num(max);
  });
  document.querySelectorAll("[data-credit-meter]").forEach((el) => {
    el.style.width = `${pct}%`;
  });
  document.querySelectorAll("[data-plan-label]").forEach((el) => {
    el.textContent = `${PLAN_NAMES[plan] || "Creator"} plan`;
  });
}

syncAccount();

// ---------- API key copy ----------
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const key = button.dataset.copy;
    const masked = `${key.slice(0, 8)}••••${key.slice(-4)}`;
    const copied = await FF.copyText(key);
    button.textContent = copied ? "Copied" : masked;
    FF.toast(copied ? "API key copied to clipboard" : `Full key: ${masked}`);
    setTimeout(() => {
      button.textContent = "Copy";
    }, 1800);
  });
});
