/* ============ EchoID Studio — live + recorded transcription (demo) ============ */
(() => {
  const $ = (s) => document.querySelector(s);
  const modeLive = $("#modeLive"), modeFile = $("#modeFile");
  const livePanel = $("#livePanel"), filePanel = $("#filePanel");
  const micBtn = $("#micBtn"), micTimer = $("#micTimer"), micStatus = $("#micStatus");
  const dropzone = $("#dropzone"), fileInput = $("#fileInput"), fileName = $("#fileName");
  const transcribeBtn = $("#transcribeBtn"), progress = $("#progress");
  const titleInput = $("#titleInput"), saveBtn = $("#saveBtn");
  const stageWave = $("#stageWave"), audioBar = $("#audioBar"), player = $("#player"), playBtn = $("#playBtn");
  const emptyStage = $("#emptyStage"), segList = $("#segList"), legend = $("#legend");
  const dlBtns = [...document.querySelectorAll("[data-dl]")];

  let current = null;          // working transcript
  let recording = false;
  let mediaStream = null, audioCtx = null, analyser = null, rafId = null, recorder = null, chunks = [];
  let startedAt = 0, tickId = null, simId = null;

  const SIM_LINES = [
    "Alright, let's get started.", "Can everyone hear me clearly?",
    "I'll share the numbers in a second.", "Sounds good — go ahead.",
    "The main blocker was the data migration.", "We shipped the fix this morning.",
    "Any questions before we move on?", "Yes — what's the timeline for that?",
    "Let's park that for next week.", "Great, that wraps it up.",
  ];
  let simIdx = 0;

  /* ---------- helpers ---------- */
  const speakerColor = (name) => ECHO.COLORS[(current.speakers.indexOf(name) + ECHO.COLORS.length) % ECHO.COLORS.length];

  function ensureSpeaker(name) {
    if (!current.speakers.includes(name)) current.speakers.push(name);
    return name;
  }

  function addSegment(speaker, text, atSec) {
    ensureSpeaker(speaker);
    current.segments.push({ id: crypto.randomUUID(), speaker, start: atSec, end: atSec + 4, text });
    render();
    segList.scrollTop = segList.scrollHeight;
  }

  function buildTranscript() {
    return {
      id: current.id, title: (titleInput.value.trim() || "Untitled transcript"),
      source: current.source, createdAt: current.createdAt, durationMs: current.durationMs,
      speakers: current.speakers, segments: current.segments,
    };
  }

  function startNew(source) {
    current = { id: crypto.randomUUID(), source, createdAt: Date.now(), durationMs: 0, speakers: [], segments: [] };
    simIdx = 0;
    render();
  }

  /* ---------- rendering ---------- */
  function render() {
    const has = current && current.segments.length;
    emptyStage.hidden = !!has;
    segList.hidden = !has;
    legend.hidden = !has;
    if (!has) { dlBtns.forEach((b) => (b.disabled = true)); saveBtn.disabled = true; renderLegend(); return; }

    segList.innerHTML = "";
    for (const s of current.segments) {
      const row = document.createElement("div");
      row.className = "seg";
      row.style.setProperty("--c", speakerColor(s.speaker));

      const spk = document.createElement("button");
      spk.className = "seg__speaker"; spk.type = "button"; spk.textContent = s.speaker;
      spk.title = "Rename speaker";
      spk.addEventListener("click", () => renameSpeaker(s.speaker));

      const time = document.createElement("span");
      time.className = "seg__time";
      time.textContent = ECHO.fmtStamp(s.start);

      const txt = document.createElement("input");
      txt.className = "seg__text"; txt.value = s.text;
      txt.addEventListener("change", () => { s.text = txt.value; });

      const del = document.createElement("button");
      del.className = "seg__del"; del.type = "button"; del.setAttribute("aria-label", "Delete line");
      del.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>';
      del.addEventListener("click", () => {
        current.segments = current.segments.filter((x) => x.id !== s.id);
        render();
      });

      row.append(spk, time, txt, del);
      segList.append(row);
    }
    renderLegend();
    dlBtns.forEach((b) => (b.disabled = false));
    saveBtn.disabled = false;
  }

  function renderLegend() {
    legend.innerHTML = "";
    if (!current) return;
    for (const name of current.speakers) {
      const tag = document.createElement("span");
      const dot = document.createElement("i");
      dot.style.setProperty("--c", speakerColor(name));
      tag.append(dot, document.createTextNode(name));
      legend.append(tag);
    }
  }

  /* ---------- rename modal ---------- */
  function renameSpeaker(oldName) {
    const back = document.createElement("div");
    back.className = "modal-back";
    back.innerHTML = `<div class="modal"><h3>Rename speaker</h3>
      <div class="field"><input id="rnInput" maxlength="24" value="${oldName.replace(/"/g, "&quot;")}" /></div>
      <div class="modal__actions"><button class="btn btn--ghost btn--sm" data-x="cancel">Cancel</button>
      <button class="btn btn--solid btn--sm" data-x="ok">Rename</button></div></div>`;
    document.body.append(back);
    requestAnimationFrame(() => back.classList.add("is-open"));
    const input = back.querySelector("#rnInput");
    input.focus(); input.select();
    const close = () => { back.classList.remove("is-open"); setTimeout(() => back.remove(), 250); };
    back.addEventListener("click", (e) => {
      if (e.target === back || e.target.closest('[data-x="cancel"]')) close();
      if (e.target.closest('[data-x="ok"]')) {
        const nv = input.value.trim();
        if (nv && nv !== oldName) {
          current.speakers = current.speakers.map((s) => (s === oldName ? nv : s));
          current.segments.forEach((s) => { if (s.speaker === oldName) s.speaker = nv; });
          render();
        }
        close();
      }
    });
    input.addEventListener("keydown", (e) => e.key === "Enter" && back.querySelector('[data-x="ok"]').click());
  }

  /* ---------- mode switching ---------- */
  function setMode(live) {
    modeLive.classList.toggle("is-active", live);
    modeFile.classList.toggle("is-active", !live);
    modeLive.setAttribute("aria-selected", String(live));
    modeFile.setAttribute("aria-selected", String(!live));
    livePanel.hidden = !live;
    filePanel.hidden = live;
    if (recording) stopLive();
    audioBar.hidden = live ? true : !player.src;
    stageWave.classList.remove("is-live");
  }
  modeLive.addEventListener("click", () => setMode(true));
  modeFile.addEventListener("click", () => setMode(false));

  /* ---------- live mic ---------- */
  const bars = [...stageWave.querySelectorAll("i")];

  function driveWaveFromAnalyser() {
    const data = new Uint8Array(analyser.frequencyBinCount);
    const loop = () => {
      analyser.getByteFrequencyData(data);
      const n = Math.floor(data.length / bars.length);
      bars.forEach((b, i) => {
        let sum = 0;
        for (let j = 0; j < n; j++) sum += data[i * n + j];
        b.style.height = Math.max(12, (sum / n / 255) * 100) + "%";
      });
      rafId = requestAnimationFrame(loop);
    };
    loop();
  }

  async function startLive() {
    startNew("live");
    titleInput.value = "";
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioCtx = new AudioContext();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      audioCtx.createMediaStreamSource(mediaStream).connect(analyser);
      driveWaveFromAnalyser();
      try { recorder = new MediaRecorder(mediaStream); recorder.ondataavailable = (e) => chunks.push(e.data); recorder.start(); } catch { recorder = null; }
      micStatus.textContent = "Listening — EchoID is identifying speakers…";
    } catch {
      recorder = null;
      micStatus.textContent = "Mic unavailable — running a simulated session.";
      stageWave.classList.add("is-live");
      ECHO.toast("Microphone blocked — showing a simulated session instead.");
    }
    recording = true;
    micBtn.classList.add("is-rec");
    startedAt = Date.now();
    tickId = setInterval(() => {
      const ms = Date.now() - startedAt;
      micTimer.textContent = ECHO.fmtClock(ms);
      current.durationMs = ms;
    }, 500);
    const speak = () => {
      const who = ECHO.SPEAKERS[simIdx % 3 === 0 ? 0 : simIdx % 4];
      addSegment(who, SIM_LINES[simIdx % SIM_LINES.length], Math.floor((Date.now() - startedAt) / 1000));
      simIdx++;
    };
    speak();
    simId = setInterval(speak, 4200);
  }

  function stopLive() {
    if (!recording) return;
    recording = false;
    micBtn.classList.remove("is-rec");
    clearInterval(tickId); clearInterval(simId);
    cancelAnimationFrame(rafId);
    stageWave.classList.remove("is-live");
    bars.forEach((b) => (b.style.height = ""));
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        player.src = URL.createObjectURL(blob);
        audioBar.hidden = false;
      };
      recorder.stop();
    }
    mediaStream?.getTracks().forEach((t) => t.stop());
    audioCtx?.close().catch(() => {});
    mediaStream = null; analyser = null; audioCtx = null; chunks = [];
    micStatus.textContent = "Session finished. Review the transcript, then save or download it.";
    if (current && current.segments.length) {
      current.durationMs = Date.now() - startedAt;
      render();
    }
  }

  micBtn.addEventListener("click", () => (recording ? stopLive() : startLive().catch(() => ECHO.toast("Could not start the session."))));

  /* ---------- file upload ---------- */
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && fileInput.click());
  ["dragover", "dragenter"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("is-over"); }));
  dropzone.addEventListener("drop", (e) => e.dataTransfer.files[0] && pickFile(e.dataTransfer.files[0]));
  fileInput.addEventListener("change", () => fileInput.files[0] && pickFile(fileInput.files[0]));

  let pickedFile = null;
  function pickFile(f) {
    if (!/^(audio|video)\//.test(f.type) && !/\.(mp3|wav|m4a|ogg|flac|webm)$/i.test(f.name)) {
      return ECHO.toast("Please choose an audio file.");
    }
    pickedFile = f;
    fileName.textContent = `${f.name} · ${(f.size / 1048576).toFixed(1)} MB`;
    transcribeBtn.disabled = false;
    player.src = URL.createObjectURL(f);
  }

  transcribeBtn.addEventListener("click", () => {
    if (!pickedFile) return;
    startNew("file");
    titleInput.value = pickedFile.name.replace(/\.[^.]+$/, "").slice(0, 80);
    transcribeBtn.disabled = true;
    progress.hidden = false;
    const bar = progress.firstElementChild;
    let p = 0;
    const iv = setInterval(() => {
      p = Math.min(100, p + 7 + Math.random() * 12);
      bar.style.width = p + "%";
      if (p >= 100) {
        clearInterval(iv);
        setTimeout(finishFileTranscription, 350);
      }
    }, 180);
  });

  function finishFileTranscription() {
    progress.hidden = true;
    progress.firstElementChild.style.width = "0%";
    transcribeBtn.disabled = false;
    audioBar.hidden = false;
    const dur = Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 60;
    current.durationMs = dur * 1000;
    const n = Math.max(4, Math.min(8, Math.round(dur / 18)));
    for (let i = 0; i < n; i++) {
      const who = ECHO.SPEAKERS[i % Math.min(3, ECHO.SPEAKERS.length)];
      addSegment(who, SIM_LINES[(simIdx++) % SIM_LINES.length], Math.floor((i * dur) / n));
    }
    micStatus.textContent = "";
    ECHO.toast("Transcription ready — verify the speaker labels.");
  }

  /* ---------- playback waveform ---------- */
  playBtn.addEventListener("click", () => (player.paused ? player.play() : player.pause()));
  player.addEventListener("play", () => { stageWave.classList.add("is-live"); playBtn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>'; });
  player.addEventListener("pause", () => { stageWave.classList.remove("is-live"); playBtn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7L8 5z"/></svg>'; });

  /* ---------- title / save / download ---------- */
  titleInput.addEventListener("input", () => { if (current) current.title = titleInput.value; });

  saveBtn.addEventListener("click", () => {
    if (!current || !current.segments.length) return;
    if (!ECHO.session()) {
      ECHO.toast("Log in to save transcripts to your history…");
      setTimeout(() => (location.href = "login.html?next=" + encodeURIComponent("products.html")), 1100);
      return;
    }
    const t = buildTranscript();
    ECHO.saveTranscript(t);
    saveBtn.textContent = "Saved ✓";
    setTimeout(() => (saveBtn.textContent = "Save to history"), 1800);
    ECHO.toast(`"${t.title}" saved to history.`);
  });

  dlBtns.forEach((b) =>
    b.addEventListener("click", () => {
      if (!current) return;
      ECHO.download(buildTranscript(), b.dataset.dl);
      ECHO.toast(`Downloading ${b.dataset.dl.toUpperCase()}…`);
    })
  );
})();
