/* ============ EchoID history ============ */
(() => {
  if (!ECHO.requireAuth()) return;

  const rows = document.getElementById("rows");
  const empty = document.getElementById("empty");
  const search = document.getElementById("search");
  const filterSource = document.getElementById("filterSource");
  const sortBy = document.getElementById("sortBy");

  const ICON = {
    view: '<svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/></svg>',
    del: '<svg viewBox="0 0 24 24"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>',
  };
  const esc = (s) => { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; };

  function visible() {
    const q = search.value.trim().toLowerCase();
    const src = filterSource.value;
    let list = ECHO.transcripts().filter(
      (t) =>
        (!src || t.source === src) &&
        (!q || t.title.toLowerCase().includes(q) || (t.speakers || []).some((s) => s.toLowerCase().includes(q)))
    );
    const by = sortBy.value;
    list.sort((a, b) => (by === "old" ? a.createdAt - b.createdAt : by === "dur" ? b.durationMs - a.durationMs : b.createdAt - a.createdAt));
    return list;
  }

  function render() {
    const list = visible();
    rows.innerHTML = "";
    empty.hidden = list.length > 0;
    for (const t of list) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="t-title">${esc(t.title)}</td>
        <td><span class="badge badge--${t.source}">${t.source === "live" ? "Live" : "Recording"}</span></td>
        <td>${ECHO.fmtDate(t.createdAt)}</td>
        <td>${ECHO.fmtDuration(t.durationMs)}</td>
        <td>${(t.speakers || []).length}</td>
        <td><div class="row-actions" style="justify-content:flex-end"></div></td>`;
      const acts = tr.querySelector(".row-actions");

      const view = document.createElement("button");
      view.className = "icon-btn"; view.title = "View transcript"; view.innerHTML = ICON.view;
      view.addEventListener("click", () => openModal(t.id));

      const del = document.createElement("button");
      del.className = "icon-btn icon-btn--del"; del.title = "Delete"; del.innerHTML = ICON.del;
      del.addEventListener("click", () => confirmDelete(t));

      acts.append(view, del);
      tr.addEventListener("click", (e) => !e.target.closest("button") && openModal(t.id));
      rows.append(tr);
    }
  }

  /* ---------- view modal with downloads ---------- */
  function openModal(id) {
    const t = ECHO.getTranscript(id);
    if (!t) return;
    const color = (name) => ECHO.COLORS[(t.speakers.indexOf(name) + ECHO.COLORS.length) % ECHO.COLORS.length];
    const back = document.createElement("div");
    back.className = "modal-back";
    back.innerHTML = `
      <div class="modal" style="width:min(560px,94%);max-height:82vh;display:flex;flex-direction:column">
        <h3 style="margin-bottom:2px">${esc(t.title)}</h3>
        <p style="font-size:0.8rem;color:var(--muted);margin-bottom:14px">
          ${t.source === "live" ? "Live session" : "Recording"} · ${ECHO.fmtDate(t.createdAt)} · ${ECHO.fmtDuration(t.durationMs)}
        </p>
        <div class="seg-list" style="max-height:none;overflow:auto;flex:1">
          ${t.segments.map((s) => `
            <div class="seg" style="grid-template-columns:74px 1fr">
              <button class="seg__speaker" style="--c:${color(s.speaker)};cursor:default">${esc(s.speaker)}</button>
              <div><span class="seg__time">[${ECHO.fmtStamp(s.start)}]</span> ${esc(s.text)}</div>
            </div>`).join("")}
        </div>
        <div class="download-row" style="margin-top:18px">
          <button class="btn btn--solid btn--sm" data-k="json">JSON</button>
          <button class="btn btn--solid btn--sm" data-k="txt">Text</button>
          <button class="btn btn--solid btn--sm" data-k="pdf">PDF</button>
        </div>
        <button class="btn btn--ghost btn--sm" data-close style="margin-top:12px;justify-content:center">Close</button>
      </div>`;
    document.body.append(back);
    requestAnimationFrame(() => back.classList.add("is-open"));
    const close = () => { back.classList.remove("is-open"); setTimeout(() => back.remove(), 250); history.replaceState(null, "", location.pathname); };
    back.addEventListener("click", (e) => {
      const k = e.target.closest("[data-k]")?.dataset.k;
      if (k) { ECHO.download(t, k); ECHO.toast(`Downloading ${k.toUpperCase()}…`); return; }
      if (e.target === back || e.target.closest("[data-close]")) close();
    });
    document.addEventListener("keydown", function esc1(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc1); } });
  }

  /* ---------- delete confirm ---------- */
  function confirmDelete(t) {
    const back = document.createElement("div");
    back.className = "modal-back";
    back.innerHTML = `
      <div class="modal">
        <h3>Delete transcript?</h3>
        <p style="color:var(--muted);font-size:0.9rem;margin-bottom:18px">“${esc(t.title)}” will be removed permanently.</p>
        <div class="modal__actions">
          <button class="btn btn--ghost btn--sm" data-x="cancel">Keep it</button>
          <button class="btn btn--danger btn--sm" data-x="ok">Delete</button>
        </div>
      </div>`;
    document.body.append(back);
    requestAnimationFrame(() => back.classList.add("is-open"));
    back.addEventListener("click", (e) => {
      const close = () => { back.classList.remove("is-open"); setTimeout(() => back.remove(), 250); };
      if (e.target === back || e.target.closest('[data-x="cancel"]')) close();
      if (e.target.closest('[data-x="ok"]')) { ECHO.deleteTranscript(t.id); close(); render(); ECHO.toast("Transcript deleted."); }
    });
  }

  [search, filterSource, sortBy].forEach((el) => el.addEventListener("input", render));
  render();

  const open = new URLSearchParams(location.search).get("open");
  if (open) openModal(open);
})();
