/* ================= EchoID interactions ================= */

const header = document.getElementById("header");
const menuToggle = document.getElementById("menuToggle");
const menuClose = document.getElementById("menuClose");
const mobileMenu = document.getElementById("mobileMenu");

/* ---------- Mobile full-screen menu ---------- */
function setMenu(open) {
  mobileMenu.classList.toggle("is-open", open);
  mobileMenu.setAttribute("aria-hidden", String(!open));
  menuToggle.setAttribute("aria-expanded", String(open));
  document.body.style.overflow = open ? "hidden" : "";
}

menuToggle.addEventListener("click", () => setMenu(true));
menuClose.addEventListener("click", () => setMenu(false));
mobileMenu.querySelectorAll(".mobile-menu__link").forEach((link) =>
  link.addEventListener("click", () => setMenu(false))
);
document.addEventListener("keydown", (e) => e.key === "Escape" && setMenu(false));

/* ---------- Scroll-spy: highlight active nav link ---------- */
const sections = [...document.querySelectorAll("main section[id]")];
const navLinks = [...document.querySelectorAll(".nav__link, .mobile-menu__link")];

function setActive(id) {
  navLinks.forEach((l) =>
    l.classList.toggle("is-active", l.getAttribute("href") === `#${id}`)
  );
}

const spy = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => e.isIntersecting && setActive(e.target.id));
  },
  { rootMargin: "-45% 0px -50% 0px" }
);
sections.forEach((s) => spy.observe(s));

/* ---------- Reveal on scroll ---------- */
const revealer = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("is-visible");
        revealer.unobserve(e.target);
      }
    });
  },
  { threshold: 0.15 }
);
document.querySelectorAll(".reveal").forEach((el) => revealer.observe(el));

/* ---------- Hero live-audio demo ---------- */
const voiceCard = document.querySelector(".voice-card");
const liveBtn = document.getElementById("liveBtn");
const srcLabel = document.getElementById("srcLabel");
const transcript = document.getElementById("transcript");

const recordedLines = [
  { who: "Alex", color: "#f7b500", text: "Did the Q3 numbers land yet?" },
  { who: "Priya", color: "#7fd1c1", text: "Uploading the deck now." },
];

const liveLines = [
  { who: "Speaker 1", color: "#f7b500", text: "Alright, everyone's on the line —" },
  { who: "Speaker 2", color: "#7fd1c1", text: "Can you hear me okay?" },
  { who: "Speaker 1", color: "#f7b500", text: "Loud and clear. Starting the recording." },
  { who: "Speaker 3", color: "#f2784b", text: "Great, I'll take notes this time." },
  { who: "Speaker 2", color: "#7fd1c1", text: "First item: the launch timeline." },
  { who: "Speaker 1", color: "#f7b500", text: "Right — two weeks of buffer, agreed?" },
];

let liveTimer = null;
let liveIndex = 0;

function addLine({ who, color, text }) {
  const li = document.createElement("li");
  li.style.setProperty("--c", color);
  const b = document.createElement("b");
  b.textContent = who;
  const span = document.createElement("span");
  span.textContent = text;
  li.append(b, span);
  transcript.append(li);
  while (transcript.children.length > 3) transcript.firstElementChild.remove();
}

function startLive() {
  voiceCard.classList.add("is-live");
  srcLabel.textContent = "Live stream · identifying speakers";
  liveBtn.textContent = "Stop demo";
  transcript.innerHTML = "";
  liveIndex = 0;
  addLine(liveLines[0]);
  liveTimer = setInterval(() => {
    liveIndex = (liveIndex + 1) % liveLines.length;
    addLine(liveLines[liveIndex]);
  }, 1800);
}

function stopLive() {
  voiceCard.classList.remove("is-live");
  srcLabel.textContent = "Sample call · recorded";
  liveBtn.textContent = "Simulate live audio";
  clearInterval(liveTimer);
  liveTimer = null;
  transcript.innerHTML = "";
  recordedLines.forEach(addLine);
}

liveBtn.addEventListener("click", () => (liveTimer ? stopLive() : startLive()));

/* ---------- Plan selection ---------- */
document.querySelectorAll(".plan-card__cta").forEach((btn) => {
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".plan-card__cta")
      .forEach((b) => b !== btn && b.classList.remove("is-chosen"));
    btn.classList.toggle("is-chosen");
  });
});
