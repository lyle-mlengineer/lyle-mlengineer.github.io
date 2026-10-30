/* ============ EchoID shared app helpers ============ */
/* Demo-only client-side "backend": all data lives in localStorage.
   Auth here is a UI mock — never use it for real credentials. */

const ECHO = (() => {
  const K = { users: "echoid.users", session: "echoid.session", t: "echoid.transcripts" };

  const read = (k, fb) => { try { return JSON.parse(localStorage.getItem(k)) ?? fb; } catch { return fb; } };
  const write = (k, v) => localStorage.setItem(k, JSON.stringify(v));

  /* ---------- accounts / session ---------- */
  function accounts() { return read(K.users, []); }
  function saveAccount(a) { const list = accounts(); list.push(a); write(K.users, list); }
  function updateAccount(email, patch) {
    const list = accounts().map((u) => (u.email.toLowerCase() === email.toLowerCase() ? { ...u, ...patch } : u));
    write(K.users, list);
  }
  function findAccount(email) { return accounts().find((u) => u.email.toLowerCase() === email.toLowerCase()); }
  function session() { return read(K.session, null); }
  function signIn(email) { write(K.session, { email, at: Date.now() }); }
  function signOut() { localStorage.removeItem(K.session); }
  function currentUser() {
    const s = session();
    return s ? findAccount(s.email) || null : null;
  }

  /* ---------- transcripts ---------- */
  function transcripts() { return read(K.t, []); }
  function saveTranscript(t) {
    const list = transcripts();
    const i = list.findIndex((x) => x.id === t.id);
    if (i >= 0) list[i] = t; else list.unshift(t);
    write(K.t, list);
  }
  function deleteTranscript(id) { write(K.t, transcripts().filter((t) => t.id !== id)); }
  function getTranscript(id) { return transcripts().find((t) => t.id === id) || null; }

  /* ---------- demo data ---------- */
  function seed() {
    if (!findAccount("demo@echoid.ai")) {
      saveAccount({ name: "Demo User", email: "demo@echoid.ai", pass: btoa("demo123"), plan: "growth", createdAt: Date.now() });
    }
    if (transcripts().length === 0) {
      const day = 864e5, now = Date.now();
      const mk = (title, source, ago, durSec, segs) => ({
        id: crypto.randomUUID(), title, source, createdAt: now - ago, durationMs: durSec * 1000,
        speakers: segs.reduce((acc, s) => (acc.includes(s.who) || acc.push(s.who), acc), []),
        segments: segs.map((s, i) => ({ id: i, speaker: s.who, start: i * 6, end: i * 6 + 5, text: s.text })),
      });
      const SPEAKERS = ["Alex", "Priya", "Marc", "June"];
      write(K.t, [
        mk("Q3 board prep — recording", "file", 2 * day, 214, [
          { who: "Alex", text: "Let's walk through the ARR slide first." },
          { who: "Priya", text: "Net retention came in at 118 percent." },
          { who: "Alex", text: "Great — put that one up front." },
        ]),
        mk("Support standup — live", "live", 5 * day, 305, [
          { who: "Marc", text: "Ticket queue is back under control." },
          { who: "June", text: "The callback bot caught two escalations." },
          { who: "Marc", text: "Nice. Anything else before we wrap?" },
        ]),
        mk("Podcast episode 12 — raw cut", "file", 9 * day, 428, [
          { who: "Priya", text: "Welcome back to Signal & Noise." },
          { who: "June", text: "Today we're talking about voice biometrics." },
          { who: "Priya", text: "Let's get into it." },
        ]),
      ]);
    }
  }

  /* ---------- formatting ---------- */
  const fmtClock = (ms) => {
    const s = Math.max(0, Math.floor(ms / 1000));
    return [Math.floor(s / 60), s % 60].map((n) => String(n).padStart(2, "0")).join(":");
  };
  const fmtStamp = (sec) => {
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
    return (h ? h + ":" : "") + [m, s].map((n) => String(n).padStart(2, "0")).join(":");
  };
  const fmtDate = (ts) => new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  const fmtDuration = (ms) => fmtClock(ms);

  /* ---------- downloads ---------- */
  function blobDownload(content, filename, mime) {
    const blob = content instanceof Blob ? content : new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }
  const safeName = (t) => (t || "transcript").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "transcript";

  function toJSON(t) {
    return JSON.stringify({
      title: t.title, source: t.source, createdAt: new Date(t.createdAt).toISOString(),
      durationSeconds: Math.round(t.durationMs / 1000), speakers: t.speakers,
      segments: t.segments.map((s) => ({ speaker: s.speaker, start: s.start, end: s.end, text: s.text })),
    }, null, 2);
  }
  function toText(t) {
    const head = `${t.title}\nRecorded ${fmtDate(t.createdAt)} · ${fmtDuration(t.durationMs)} · ${t.speakers.length} speakers\n${"=".repeat(56)}`;
    return head + "\n\n" + t.segments.map((s) => `[${fmtStamp(s.start)}] ${s.speaker}: ${s.text}`).join("\n") + "\n";
  }

  /* Minimal dependency-free PDF writer (Helvetica, latin-1 only). */
  function toPDF(t) {
    const esc = (s) => s.replace(/[^\x20-\x7E]/g, (c) => ({ "—": "-", "–": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "…": "..." }[c] || "")).replace(/[\\()]/g, (c) => "\\" + c);
    const wrap = (s, w) => { const out = []; let line = ""; for (const word of s.split(/\s+/)) { if ((line + " " + word).trim().length > w) { out.push(line.trim()); line = word; } else line += " " + word; } if (line.trim()) out.push(line.trim()); return out; };
    const lines = [];
    lines.push({ txt: esc(t.title.slice(0, 60)), size: 18, gap: 10 });
    lines.push({ txt: esc(`${fmtDate(t.createdAt)}  |  ${fmtDuration(t.durationMs)}  |  ${t.speakers.length} speakers`), size: 9, gap: 16 });
    for (const s of t.segments) {
      const body = wrap(esc(s.text), 86);
      lines.push({ txt: `[${fmtStamp(s.start)}]  ${esc(s.speaker)}`, size: 10, bold: true, gap: 3 });
      body.forEach((b, i) => lines.push({ txt: b, size: 10, gap: i === body.length - 1 ? 12 : 2 }));
    }
    const pages = []; let page = [], y = 780;
    for (const L of lines) {
      const h = L.size + L.gap;
      if (y - h < 50) { pages.push(page); page = []; y = 780; }
      page.push({ ...L, y }); y -= h;
    }
    if (page.length) pages.push(page);

    const objs = [];
    const addObj = (body) => { objs.push(body); return objs.length; };
    const pagesNum = 3 + pages.length * 2 + 1;
    const fontR = addObj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
    const fontB = addObj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>");
    const kids = [];
    for (const pg of pages) {
      let stream = "BT\n";
      for (const L of pg) {
        stream += `/${L.bold ? "F2" : "F1"} ${L.size} Tf\n1 0 0 1 56 ${L.y} Tm\n0 0 0 rg\n(${L.txt}) Tj\n`;
      }
      stream += "ET";
      const sNum = addObj(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
      const pNum = addObj(`<< /Type /Page /Parent ${pagesNum} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 ${fontR} 0 R /F2 ${fontB} 0 R >> >> /Contents ${sNum} 0 R >>`);
      kids.push(pNum);
    }
    addObj(`<< /Type /Pages /Kids [${kids.map((n) => n + " 0 R").join(" ")}] /Count ${kids.length} >>`);
    const rootNum = addObj(`<< /Type /Catalog /Pages ${pagesNum} 0 R >>`);

    let pdf = "%PDF-1.4\n";
    const offsets = [0];
    objs.forEach((b, i) => { offsets.push(pdf.length); pdf += `${i + 1} 0 obj\n${b}\nendobj\n`; });
    const xref = pdf.length;
    pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
    for (let i = 1; i <= objs.length; i++) pdf += String(offsets[i]).padStart(10, "0") + " 00000 n \n";
    pdf += `trailer\n<< /Size ${objs.length + 1} /Root ${rootNum} 0 R >>\nstartxref\n${xref}\n%%EOF`;
    return pdf;
  }

  function download(t, kind) {
    const name = safeName(t.title);
    if (kind === "json") blobDownload(toJSON(t), `${name}.json`, "application/json");
    else if (kind === "txt") blobDownload(toText(t), `${name}.txt`, "text/plain");
    else blobDownload(toPDF(t), `${name}.pdf`, "application/pdf");
  }

  /* ---------- UI: toasts ---------- */
  function toast(msg, ms = 2600) {
    let box = document.querySelector(".toast-box");
    if (!box) { box = document.createElement("div"); box.className = "toast-box"; document.body.append(box); }
    const el = document.createElement("div");
    el.className = "toast"; el.textContent = msg;
    box.append(el);
    setTimeout(() => { el.classList.add("is-out"); setTimeout(() => el.remove(), 350); }, ms);
  }

  /* ---------- UI: app header wiring ---------- */
  function initHeader() {
    const toggle = document.getElementById("menuToggle");
    const close = document.getElementById("menuClose");
    const menu = document.getElementById("mobileMenu");
    if (toggle && menu) {
      const set = (open) => {
        menu.classList.toggle("is-open", open);
        menu.setAttribute("aria-hidden", String(!open));
        toggle.setAttribute("aria-expanded", String(open));
        document.body.style.overflow = open ? "hidden" : "";
      };
      toggle.addEventListener("click", () => set(true));
      close?.addEventListener("click", () => set(false));
      menu.querySelectorAll("a").forEach((l) => l.addEventListener("click", () => set(false)));
      document.addEventListener("keydown", (e) => e.key === "Escape" && set(false));
    }
    const chip = document.getElementById("userChip");
    const user = currentUser();
    if (chip) {
      if (user) {
        chip.innerHTML = `<span class="user-chip__avatar">${user.name.trim().charAt(0).toUpperCase()}</span><span>${user.name.split(" ")[0]}</span><a href="#" class="user-chip__out" id="signOut">Log out</a>`;
        chip.addEventListener("click", (e) => {
          if (e.target.id === "signOut") { e.preventDefault(); signOut(); location.href = "index.html"; }
        });
      } else {
        chip.innerHTML = `<a href="login.html" class="btn btn--ghost btn--sm" style="padding:9px 22px">Log in</a>`;
      }
    }
  }

  /* ---------- guard: pages that require a session ---------- */
  function requireAuth() {
    if (!session()) {
      const back = location.pathname.split("/").pop() + location.search;
      location.href = "login.html?next=" + encodeURIComponent(back);
      return false;
    }
    return true;
  }

  return { seed, accounts, saveAccount, updateAccount, findAccount, signIn, signOut, currentUser, session, transcripts, saveTranscript, deleteTranscript, getTranscript, fmtClock, fmtStamp, fmtDate, fmtDuration, download, blobDownload, toast, initHeader, requireAuth, SPEAKERS: ["Alex", "Priya", "Marc", "June"], COLORS: ["#f7b500", "#7fd1c1", "#f2784b", "#b48ef2", "#5da9ff", "#ff8fb3"] };
})();

ECHO.seed();
document.addEventListener("DOMContentLoaded", ECHO.initHeader);
