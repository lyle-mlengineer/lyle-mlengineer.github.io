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

// Count-up animation for the stats
const counters = document.querySelectorAll(".count");
const easeOut = (t) => 1 - Math.pow(1 - t, 3);

function animateCount(el) {
  const target = parseFloat(el.dataset.target);
  const decimals = parseInt(el.dataset.decimals, 10);
  const duration = 1400;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    el.textContent = (target * easeOut(progress)).toFixed(decimals);
    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCount(entry.target);
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.6 }
);

counters.forEach((counter) => observer.observe(counter));

// Subtle parallax on the floating collage decorations
const collage = document.querySelector(".hero-collage");
const floaters = collage.querySelectorAll(".badge-hours, .badge-avatars, .sparkle");

document.querySelector(".hero-card").addEventListener("mousemove", (e) => {
  const rect = collage.getBoundingClientRect();
  const x = (e.clientX - (rect.left + rect.width / 2)) / rect.width;
  const y = (e.clientY - (rect.top + rect.height / 2)) / rect.height;

  floaters.forEach((el, i) => {
    const depth = (i + 1) * 5;
    el.style.translate = `${x * depth}px ${y * depth}px`;
  });
});

// Contact form (front-end only — no endpoint wired up)
const contactForm = document.getElementById("contactForm");
const formStatus = document.getElementById("formStatus");

contactForm.addEventListener("submit", (e) => {
  e.preventDefault();
  formStatus.textContent = "Thanks — we'll reply within one working day.";
  contactForm.reset();
});
