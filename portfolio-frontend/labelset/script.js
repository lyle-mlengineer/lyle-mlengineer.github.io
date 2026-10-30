/* Labelset — interactions */
(() => {
  "use strict";

  /* ---------- Sticky header state ---------- */
  const header = document.getElementById("header");
  const onScrollHeader = () => header.classList.toggle("is-scrolled", window.scrollY > 40);
  window.addEventListener("scroll", onScrollHeader, { passive: true });
  onScrollHeader();

  /* ---------- Mobile menu ---------- */
  const toggle = document.getElementById("nav-toggle");
  const menu = document.getElementById("nav-menu");

  const closeMenu = () => {
    menu.classList.remove("is-open");
    toggle.classList.remove("is-open");
    toggle.setAttribute("aria-label", "Open menu");
  };
  const openMenu = () => {
    menu.classList.add("is-open");
    toggle.classList.add("is-open");
    toggle.setAttribute("aria-label", "Close menu");
  };
  toggle.addEventListener("click", () => menu.classList.contains("is-open") ? closeMenu() : openMenu());
  toggle.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle.click(); }
  });
  menu.querySelectorAll("a").forEach(a => a.addEventListener("click", closeMenu));

  /* ---------- Scroll spy ---------- */
  const links = [...document.querySelectorAll(".nav__link")];
  const sections = links
    .map(l => document.querySelector(l.getAttribute("href")))
    .filter(Boolean);

  const spy = () => {
    const pos = window.scrollY + window.innerHeight * 0.35;
    let current = sections[0];
    for (const s of sections) if (s.offsetTop <= pos) current = s;
    links.forEach(l =>
      l.classList.toggle("is-active", l.getAttribute("href") === "#" + current.id)
    );
  };
  window.addEventListener("scroll", spy, { passive: true });
  spy();

  /* ---------- Reveal on scroll ---------- */
  const revealIO = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add("is-visible");
        revealIO.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });
  document.querySelectorAll(".reveal").forEach(el => revealIO.observe(el));

  /* ---------- Animated counters ---------- */
  const animateCount = el => {
    const target = parseFloat(el.dataset.count);
    const decimals = parseInt(el.dataset.decimals || "0", 10);
    const suffix = el.dataset.suffix || "";
    const duration = 1600;
    const start = performance.now();
    const tick = now => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  const countIO = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        animateCount(e.target);
        countIO.unobserve(e.target);
      }
    });
  }, { threshold: 0.6 });
  document.querySelectorAll(".stat__number").forEach(el => countIO.observe(el));

  /* ---------- Services carousel ---------- */
  const track = document.getElementById("services-track");
  const viewport = document.getElementById("services-viewport");
  const prevBtn = document.getElementById("svc-prev");
  const nextBtn = document.getElementById("svc-next");
  let page = 0;

  const perView = () => {
    const w = window.innerWidth;
    if (w <= 600) return 1;
    if (w <= 1024) return 2;
    return 3;
  };
  const pageCount = () => Math.max(1, track.children.length - perView() + 1);

  const renderCarousel = () => {
    page = Math.min(page, pageCount() - 1);
    const card = track.children[0];
    const gap = parseFloat(getComputedStyle(track).columnGap || "0") || 24;
    const step = card.getBoundingClientRect().width + gap;
    track.style.transform = `translateX(${-page * step}px)`;
    prevBtn.disabled = page === 0;
    nextBtn.disabled = page >= pageCount() - 1;
  };

  prevBtn.addEventListener("click", () => { page = Math.max(0, page - 1); renderCarousel(); });
  nextBtn.addEventListener("click", () => { page = Math.min(pageCount() - 1, page + 1); renderCarousel(); });
  window.addEventListener("resize", renderCarousel);
  renderCarousel();

  /* ---------- Contact form ---------- */
  const form = document.getElementById("contact-form");
  const status = document.getElementById("form-status");

  form.addEventListener("submit", e => {
    e.preventDefault();
    status.classList.remove("is-error");

    let valid = true;
    form.querySelectorAll("[required]").forEach(input => {
      const bad = !input.value.trim() ||
        (input.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value));
      input.classList.toggle("invalid", bad);
      if (bad) valid = false;
    });

    if (!valid) {
      status.textContent = "Please fill in your name, a valid email and a message.";
      status.classList.add("is-error");
      return;
    }

    const role = form.role.value;
    status.textContent = role.startsWith("Organization")
      ? "Thanks! Our team will quote your project within one business day."
      : role.startsWith("Worker")
        ? "You're on the list — check your inbox for the labeling skill test."
        : "Invitation confirmed — your workspace admin will assign your first tasks.";
    form.reset();
  });

  form.querySelectorAll("input, textarea").forEach(el =>
    el.addEventListener("input", () => el.classList.remove("invalid"))
  );
})();
