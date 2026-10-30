// Mobile nav toggle
const navToggle = document.getElementById("navToggle");
const navLinks = document.getElementById("navLinks");

navToggle.addEventListener("click", () => {
  const open = navLinks.classList.toggle("open");
  navToggle.classList.toggle("open", open);
  navToggle.setAttribute("aria-expanded", open);
});

navLinks.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    navLinks.classList.remove("open");
    navToggle.classList.remove("open");
    navToggle.setAttribute("aria-expanded", "false");
  });
});

// Sticky nav picks up a shadow once the page scrolls past 50px
const siteNav = document.querySelector(".site-nav");
const syncNavShadow = () => siteNav.classList.toggle("is-scrolled", window.scrollY > 50);
window.addEventListener("scroll", syncNavShadow, { passive: true });
syncNavShadow();

// ---------- Studio ----------
const PEOPLE = {
  sage: {
    name: "Audrey",
    meta: "38 · lifestyle",
    img: "images/gallery-01.png",
    alt: "AI-generated studio portrait of a smiling woman in her late thirties with auburn hair and freckles against a sage backdrop",
  },
  lilac: {
    name: "Naomi",
    meta: "28 · beauty",
    img: "images/gallery-02.png",
    alt: "AI-generated studio portrait of a smiling woman with long box braids against a lilac backdrop",
  },
  blue: {
    name: "Marcus",
    meta: "54 · executive",
    img: "images/gallery-03.png",
    alt: "AI-generated studio portrait of a smiling man in his fifties with grey hair and beard against a powder-blue backdrop",
  },
  peach: {
    name: "Kenji",
    meta: "32 · tech",
    img: "images/gallery-04.png",
    alt: "AI-generated studio portrait of a smiling man in his thirties wearing round glasses against a peach backdrop",
  },
  ivory: {
    name: "Priya",
    meta: "44 · finance",
    img: "images/gallery-05.png",
    alt: "AI-generated studio portrait of a smiling woman in her forties with a short dark bob against an ivory backdrop",
  },
  olive: {
    name: "Ellis",
    meta: "26 · travel",
    img: "images/gallery-06.png",
    alt: "AI-generated studio portrait of a smiling man in his twenties with curly hair against an olive backdrop",
  },
};

const RATIOS = {
  "4:5": { w: 1080, h: 1350 },
  "1:1": { w: 1080, h: 1080 },
  "9:16": { w: 1080, h: 1920 },
};

const state = { bg: "sage", ratio: "4:5", busy: false };
const session = [];
let displayedBg = "sage";

const genForm = document.getElementById("genForm");
const prompt = document.getElementById("prompt");
const chips = document.querySelectorAll(".chip");
const swatches = document.querySelectorAll(".swatch");
const framing = document.querySelectorAll(".seg");
const generateBtn = document.getElementById("generateBtn");
const shuffleBtn = document.getElementById("shuffleBtn");
const downloadBtn = document.getElementById("downloadBtn");
const stageFrame = document.getElementById("stageFrame");
const stageImg = document.getElementById("stageImg");
const stageLoading = document.getElementById("stageLoading");
const stageName = document.getElementById("stageName");
const stageSub = document.getElementById("stageSub");
const stageStatus = document.getElementById("stageStatus");
const thumbs = document.getElementById("sessionThumbs");

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function preload(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = resolve;
    img.onerror = resolve;
    img.src = src;
  });
}

function syncSwatches() {
  swatches.forEach((swatch) => {
    swatch.setAttribute("aria-pressed", String(swatch.dataset.bg === state.bg));
  });
}

function syncFraming() {
  framing.forEach((seg) => {
    seg.setAttribute("aria-pressed", String(seg.dataset.ratio === state.ratio));
  });
}

function syncMeta() {
  const person = PEOPLE[displayedBg];
  const dims = RATIOS[state.ratio];
  stageName.textContent = person.name;
  stageSub.textContent = `${person.meta} · ${dims.w} × ${dims.h}`;
}

function applyFace(bg) {
  const person = PEOPLE[bg];
  displayedBg = bg;
  stageImg.src = person.img;
  stageImg.alt = person.alt;
  stageFrame.dataset.ratio = state.ratio;
  syncMeta();
  downloadBtn.href = person.img;
  downloadBtn.setAttribute("download", `faceform-${person.name.toLowerCase()}.png`);
}

function renderThumbs() {
  thumbs.replaceChildren();
  session.forEach((bg) => {
    const person = PEOPLE[bg];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "session-thumb";
    btn.dataset.bg = bg;
    btn.setAttribute("aria-label", `Show ${person.name}`);
    btn.setAttribute("aria-pressed", String(bg === state.bg));

    const img = document.createElement("img");
    img.src = person.img;
    img.alt = "";
    img.loading = "lazy";

    const label = document.createElement("span");
    label.textContent = person.name;

    btn.append(img, label);
    thumbs.append(btn);
  });
}

function addThumb(bg) {
  const index = session.indexOf(bg);
  if (index !== -1) session.splice(index, 1);
  session.unshift(bg);
  renderThumbs();
}

async function renderFace() {
  if (state.busy) return;

  const person = PEOPLE[state.bg];
  state.busy = true;
  stageFrame.setAttribute("aria-busy", "true");
  stageStatus.textContent = "";
  stageLoading.hidden = false;
  generateBtn.disabled = true;
  shuffleBtn.disabled = true;

  const started = performance.now();
  const wait = 900 + Math.random() * 700;
  await Promise.all([delay(wait), preload(person.img)]);

  applyFace(state.bg);
  await delay(160);

  stageLoading.hidden = true;
  stageFrame.removeAttribute("aria-busy");
  generateBtn.disabled = false;
  shuffleBtn.disabled = false;
  state.busy = false;

  const seconds = ((performance.now() - started) / 1000).toFixed(1);
  const dims = RATIOS[state.ratio];
  stageStatus.textContent = `${person.name} rendered in ${seconds}s · ${dims.w} × ${dims.h}`;

  addThumb(state.bg);
}

genForm.addEventListener("submit", (event) => {
  event.preventDefault();
  renderFace();
});

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    chips.forEach((c) => c.classList.toggle("is-active", c === chip));
    prompt.value = chip.dataset.prompt;
    state.bg = chip.dataset.bg;
    syncSwatches();
  });
});

prompt.addEventListener("input", () => {
  chips.forEach((c) => c.classList.remove("is-active"));
});

swatches.forEach((swatch) => {
  swatch.addEventListener("click", () => {
    state.bg = swatch.dataset.bg;
    syncSwatches();
  });
});

framing.forEach((seg) => {
  seg.addEventListener("click", () => {
    state.ratio = seg.dataset.ratio;
    syncFraming();
    stageFrame.dataset.ratio = state.ratio;
    syncMeta();
  });
});

shuffleBtn.addEventListener("click", () => {
  if (state.busy) return;
  const options = Object.keys(PEOPLE).filter((bg) => bg !== state.bg);
  state.bg = options[Math.floor(Math.random() * options.length)];
  syncSwatches();
  renderFace();
});

thumbs.addEventListener("click", (event) => {
  const btn = event.target.closest(".session-thumb");
  if (!btn || state.busy) return;
  state.bg = btn.dataset.bg;
  syncSwatches();
  renderFace();
});

syncSwatches();
syncFraming();
applyFace(state.bg);
addThumb(state.bg);
