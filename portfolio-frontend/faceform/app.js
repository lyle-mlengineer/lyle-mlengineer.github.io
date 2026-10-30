// Shared helpers for the signed-in app pages
const navToggle = document.getElementById("navToggle");
const navLinks = document.getElementById("navLinks");

if (navToggle && navLinks) {
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
}

const siteNav = document.querySelector(".site-nav");

if (siteNav) {
  const syncNavShadow = () => siteNav.classList.toggle("is-scrolled", window.scrollY > 50);
  window.addEventListener("scroll", syncNavShadow, { passive: true });
  syncNavShadow();
}

const store = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(`faceform.${key}`);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`faceform.${key}`, JSON.stringify(value));
    } catch {
      /* storage unavailable — state stays in-memory for the visit */
    }
  },
};

const getCredits = () => Number(store.get("credits", 4812));
const setCredits = (value) => store.set("credits", Math.max(0, Math.round(value)));
const getPlan = () => store.get("plan", "creator");
const setPlan = (value) => store.set("plan", value);

const num = (value) => value.toLocaleString("en-US");
const money = (value) =>
  `$${value.toFixed(2)}`.replace(/\.00$/, "");

let toastTimer;
function toast(message) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    document.body.append(el);
  }
  el.textContent = message;
  requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

window.FF = {
  store,
  toast,
  copyText,
  getCredits,
  setCredits,
  getPlan,
  setPlan,
  num,
  money,
};
