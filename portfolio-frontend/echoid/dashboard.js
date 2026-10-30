/* ============ EchoID dashboard ============ */
(() => {
  if (!ECHO.requireAuth()) return;
  const user = ECHO.currentUser();
  const list = ECHO.transcripts();

  document.getElementById("greeting").textContent =
    (user ? user.name.split(" ")[0] : "Your").toUpperCase() + " DASHBOARD";

  const totalMs = list.reduce((a, t) => a + (t.durationMs || 0), 0);
  const speakers = new Set(list.flatMap((t) => t.speakers || []));
  const monthStart = new Date(); monthStart.setDate(1); monthStart.setHours(0, 0, 0, 0);
  const thisMonth = list.filter((t) => t.createdAt >= monthStart.getTime()).length;

  const mins = Math.round(totalMs / 60000);
  document.getElementById("sTotal").textContent = list.length;
  document.getElementById("sHours").textContent = mins >= 60 ? (mins / 60).toFixed(1) + "h" : mins + "m";
  document.getElementById("sSpeakers").textContent = speakers.size;
  document.getElementById("sMonth").textContent = thisMonth;

  const body = document.getElementById("recentBody");
  const empty = document.getElementById("recentEmpty");
  const recent = [...list].sort((a, b) => b.createdAt - a.createdAt).slice(0, 6);
  if (!recent.length) {
    empty.hidden = false;
  } else {
    body.innerHTML = recent.map((t) => `
      <tr data-id="${t.id}">
        <td class="t-title">${escapeHtml(t.title)}</td>
        <td><span class="badge badge--${t.source}">${t.source === "live" ? "Live" : "Recording"}</span></td>
        <td>${ECHO.fmtDate(t.createdAt)}</td>
        <td>${ECHO.fmtDuration(t.durationMs)}</td>
      </tr>`).join("");
    body.querySelectorAll("tr").forEach((tr) =>
      tr.addEventListener("click", () => (location.href = "history.html?open=" + tr.dataset.id))
    );
  }

  function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }
})();
