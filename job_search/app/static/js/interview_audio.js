/* Interview audio: tabs, the voice catalogue picker, and take generation.
   The page renders any existing take server-side; this file keeps it fresh and
   fills the pickers from /api/tts/voices. */
(function () {
    const panel = document.getElementById("interview-panel");
    if (!panel) return;

    const studio = panel.querySelector("[data-audio-studio]");
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const jobId = studio?.dataset.job;

    // -- tabs -------------------------------------------------------------
    const tabs = [...panel.querySelectorAll("[data-tab]")];
    const panels = [...panel.querySelectorAll("[data-panel]")];
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => selectTab(tab.dataset.tab));
        tab.addEventListener("keydown", (event) => {
            if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
            const index = tabs.indexOf(tab);
            const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
            selectTab(next.dataset.tab);
            next.focus();
        });
    });

    function selectTab(name) {
        tabs.forEach((tab) => {
            const active = tab.dataset.tab === name;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        panels.forEach((item) => {
            item.hidden = item.dataset.panel !== name;
        });
    }

    if (!studio) return;

    // -- scope: the whole pack or one of its sections ----------------------
    const scopeButtons = [...studio.querySelectorAll("[data-audio-scope]")];
    const sectionButtons = [...panel.querySelectorAll("[data-hear-section]")];
    const generateLabel = studio.querySelector("[data-generate-label]");
    let scope = studio.dataset.takeScope || "";
    let currentTake = null;

    function scopeTitle() {
        return scope ? titleFor(scope) : "the whole pack";
    }

    function titleFor(kind) {
        return scopeButtons.find((button) => button.dataset.audioScope === kind)?.dataset.scopeTitle
            || "that section";
    }

    function setScope(value) {
        scope = value || "";
        scopeButtons.forEach((button) => {
            const active = button.dataset.audioScope === scope;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        if (generateLabel) {
            generateLabel.textContent = scope ? "Generate this section" : "Generate audio";
        }
        if (currentTake) {
            renderTake(currentTake);
        } else {
            filterDomTurns();
        }
    }

    function visibleTurns(take) {
        return (take.turns || []).filter((turn) => !scope || turn.kind === scope);
    }

    function filterDomTurns() {
        if (!turnsList) return;
        let shown = 0;
        [...turnsList.querySelectorAll("[data-turn]")].forEach((node) => {
            const keep = !scope || node.dataset.turnKind === scope;
            node.hidden = !keep;
            if (keep) shown += 1;
        });
        if (scope && !shown) {
            setStatus(`No audio for ${scopeTitle()} yet. Generate it below.`);
        } else if (scope) {
            setStatus(`Showing ${scopeTitle()}.`);
        } else {
            setStatus("");
        }
    }

    scopeButtons.forEach((button) => {
        button.addEventListener("click", () => setScope(button.dataset.audioScope));
    });
    sectionButtons.forEach((button) => {
        button.addEventListener("click", () => {
            selectTab("audio");
            setScope(button.dataset.hearSection);
            studio.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });

    // -- voice catalogue ---------------------------------------------------
    const pickers = {
        interviewer: setupPicker(studio.querySelector('[data-picker="interviewer"]'), studio.dataset.defaultInterviewer),
        interviewee: setupPicker(studio.querySelector('[data-picker="interviewee"]'), studio.dataset.defaultInterviewee),
    };

    // -- voice modal -------------------------------------------------------
    const voiceModal = studio.querySelector("[data-voice-modal]");
    const voiceSummary = studio.querySelector("[data-voice-summary]");
    const voiceOpen = studio.querySelector("[data-voice-open]");
    let voiceSnapshot = null;

    voiceOpen?.addEventListener("click", openVoices);
    studio.querySelector("[data-voice-apply]")?.addEventListener("click", () => {
        const { interviewer, interviewee } = chosenVoices();
        if (!interviewer || !interviewee) {
            setStatus("Pick both voices first.", true);
            return;
        }
        voiceSnapshot = null;
        closeVoiceModal(false);
        setStatus("Voices updated. Generate a take to hear them.");
    });
    studio.querySelectorAll("[data-voice-close]").forEach((button) => {
        button.addEventListener("click", () => closeVoiceModal(true));
    });
    voiceModal?.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeVoiceModal(true);
    });
    voiceModal?.addEventListener("click", (event) => {
        if (event.target === voiceModal) closeVoiceModal(true);
    });

    function openVoices() {
        if (!voiceModal || voiceModal.open) return;
        updateVoiceSummary();
        voiceSnapshot = {
            interviewer: pickers.interviewer?.list?.value || "",
            interviewee: pickers.interviewee?.list?.value || "",
        };
        voiceModal.showModal();
        voiceModal.scrollTop = 0;
        voiceModal.querySelector("[data-voice-search]")?.focus();
    }

    function closeVoiceModal(revert) {
        if (!voiceModal?.open) return;
        if (revert && voiceSnapshot) {
            Object.entries(voiceSnapshot).forEach(([role, id]) => {
                const picker = pickers[role];
                if (!picker?.list || !id) return;
                if (picker.voices.some((voice) => voice.id === id)) picker.list.value = id;
                showPreview(picker);
            });
        }
        voiceSnapshot = null;
        voiceModal.close();
        updateVoiceSummary();
        voiceOpen?.focus();
    }

    function updateVoiceSummary() {
        if (!voiceSummary) return;
        Object.entries(pickers).forEach(([role, picker]) => {
            const card = voiceSummary.querySelector(`[data-summary="${role}"]`);
            if (!card) return;
            const name = card.querySelector("[data-summary-name]");
            const facts = card.querySelector("[data-summary-facts]");
            const voice = currentVoice(picker);
            const purpose = role === "interviewer" ? "Reads the questions" : "Reads your answers";
            if (!voice) {
                if (name) name.textContent = "No voice chosen";
                if (facts) facts.textContent = purpose;
                return;
            }
            if (name) name.textContent = voice.name;
            const bits = [voice.gender, voice.ethnicity, voice.accent].filter(
                (bit) => bit && bit !== "unspecified",
            );
            if (facts) {
                facts.textContent = bits.length ? `${purpose} · ${bits.join(" · ")}` : purpose;
            }
        });
    }

    function setupPicker(root, preset) {
        if (!root) return null;
        const picker = {
            root,
            search: root.querySelector("[data-voice-search]"),
            gender: root.querySelector("[data-voice-gender]"),
            ethnicity: root.querySelector("[data-voice-ethnicity]"),
            list: root.querySelector("[data-voice-select]"),
            preview: root.querySelector("[data-voice-preview]"),
            sample: root.querySelector("[data-voice-sample]"),
            preset,
            voices: [],
        };
        picker.search?.addEventListener("input", () => fillPicker(picker));
        picker.gender?.addEventListener("change", () => fillPicker(picker));
        picker.ethnicity?.addEventListener("change", () => fillPicker(picker));
        picker.list?.addEventListener("change", () => showPreview(picker));
        picker.sample?.addEventListener("click", () => playSample(picker));
        return picker;
    }

    function visibleVoices(picker) {
        const needle = (picker.search?.value || "").trim().toLowerCase();
        const gender = picker.gender?.value || "";
        const ethnicity = picker.ethnicity?.value || "";
        return picker.voices.filter((voice) => {
            if (gender && voice.gender !== gender) return false;
            if (ethnicity && voice.ethnicity !== ethnicity) return false;
            if (!needle) return true;
            return [voice.name, voice.description, voice.accent, voice.gender,
                voice.ethnicity, ...(voice.tags || [])]
                .join(" ").toLowerCase().includes(needle);
        });
    }

    function fillPicker(picker) {
        if (!picker?.list) return;
        const chosen = picker.list.value;
        const voices = visibleVoices(picker);
        picker.list.replaceChildren(
            ...voices.map((voice) => {
                const option = document.createElement("option");
                option.value = voice.id;
                option.textContent = `${voice.name} — ${voice.gender === "unspecified" ? "voice" : voice.gender}${
                    voice.accent ? `, ${voice.accent}` : ""}`;
                return option;
            }),
        );
        if (!voices.length) {
            const option = document.createElement("option");
            option.textContent = "No voices match those filters";
            option.disabled = true;
            picker.list.append(option);
            picker.preview.replaceChildren(emptyLine("Nothing matches. Clear a filter to see voices again."));
            return;
        }
        const keep = voices.some((voice) => voice.id === chosen)
            ? chosen
            : (picker.preset && voices.some((v) => v.id === picker.preset) ? picker.preset : voices[0].id);
        picker.list.value = keep;
        picker.preset = null;
        showPreview(picker);
        updateVoiceSummary();
    }

    function currentVoice(picker) {
        return picker?.voices.find((voice) => voice.id === picker.list?.value) || null;
    }

    function showPreview(picker) {
        const voice = currentVoice(picker);
        if (!picker?.preview) return;
        if (!voice) {
            picker.preview.replaceChildren(emptyLine("Pick a voice to see what it sounds like."));
            return;
        }
        const name = element("p", "voice-picker__name", voice.name);
        const facts = element("p", "voice-picker__facts");
        const bits = [voice.gender, voice.ethnicity, voice.accent].filter(
            (bit) => bit && bit !== "unspecified",
        );
        facts.textContent = bits.length ? bits.join(" · ") : "No published description";
        const description = element("p", "voice-picker__description", voice.description || "");
        if (!description.textContent) description.remove();
        picker.preview.replaceChildren(name, facts, description);
    }

    function emptyLine(text) {
        return element("p", "voice-picker__empty", text);
    }

    function element(tag, className, text) {
        const node = document.createElement(tag);
        node.className = className;
        if (text) node.textContent = text;
        return node;
    }

    // -- samples -----------------------------------------------------------
    let sampleAudio = null;

    function playSample(picker) {
        const voice = currentVoice(picker);
        if (!voice) return;
        const button = picker.sample;
        const label = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> Loading';
        if (sampleAudio) sampleAudio.pause();
        sampleAudio = new Audio(`/api/tts/voices/${encodeURIComponent(voice.id)}/sample`);
        const restore = () => {
            button.disabled = false;
            button.innerHTML = label;
        };
        sampleAudio.addEventListener("ended", restore, { once: true });
        sampleAudio.addEventListener("error", () => {
            restore();
            setStatus(`No sample for ${voice.name}.`, true);
        }, { once: true });
        sampleAudio.play().catch(() => {
            restore();
            setStatus("The browser blocked playback. Try again.", true);
        });
    }

    // -- generation --------------------------------------------------------
    const generate = studio.querySelector("[data-audio-generate]");
    const status = studio.querySelector("[data-audio-status]");
    const meta = studio.querySelector("[data-audio-meta]");
    const turnsList = studio.querySelector("[data-audio-turns]");

    if (scope) setScope(scope);
    bindPlayers(turnsList);

    function setStatus(text, isError) {
        if (!status) return;
        status.replaceChildren();
        if (!text) return;
        status.append(element("p", isError ? "studio__status-error" : "studio__status-ok", text));
    }

    function chosenVoices() {
        const interviewer = pickers.interviewer?.list?.value;
        const interviewee = pickers.interviewee?.list?.value;
        return { interviewer, interviewee };
    }

    generate?.addEventListener("click", async () => {
        const { interviewer, interviewee } = chosenVoices();
        if (!interviewer || !interviewee) {
            setStatus("Pick both voices first.", true);
            return;
        }
        const label = generate.innerHTML;
        generate.disabled = true;
        generate.innerHTML = '<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> Starting';
        setStatus(`Writing ${scope ? scopeTitle() : "the take"}. The first turns appear as soon as they are spoken.`);
        try {
            const payload = { interviewer, interviewee };
            if (scope) payload.kind = scope;
            const response = await fetch(`/api/jobs/${jobId}/audio`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
                body: JSON.stringify(payload),
            });
            const body = await response.json().catch(() => ({}));
            if (response.status !== 202) {
                setStatus(body.error?.message || "The take could not be started.", true);
                return;
            }
            await pollTake();
        } finally {
            generate.disabled = false;
            generate.innerHTML = label;
        }
    });

    async function pollTake() {
        const started = Date.now();
        const suffix = scope ? `?kind=${encodeURIComponent(scope)}` : "";
        while (Date.now() - started < 300_000) {
            const response = await fetch(`/api/jobs/${jobId}/audio${suffix}`);
            const body = await response.json().catch(() => ({}));
            const take = body.take;
            if (!take) {
                setStatus(`No audio for ${scopeTitle()} yet. Generate it below.`);
                return;
            }
            renderTake(take);
            if (take.status === "ready") {
                setStatus(`${scope ? scopeTitle() : "Take"} ready — ${visibleTurns(take).length} turns.`);
                return;
            }
            if (take.status === "failed") {
                setStatus(take.error || "That take stopped early.", true);
                return;
            }
            setStatus(`Speaking — ${take.ready_turns} of ${take.turns.length} turns done.`);
            await new Promise((resolve) => setTimeout(resolve, 1500));
        }
        setStatus("Still generating. Refresh in a minute to see the rest.", true);
    }

    function renderTake(take) {
        if (!turnsList) return;
        currentTake = take;
        const turns = visibleTurns(take);
        turnsList.replaceChildren(...turns.map(turnNode));
        bindPlayers(turnsList);
        if (meta) {
            const seconds = Math.round(
                turns.reduce((total, turn) => total + (turn.duration_ms || 0), 0) / 1000,
            );
            meta.textContent = scope
                ? `${turns.length} turns in ${scopeTitle()} · about ${clock(seconds)} of audio`
                : `${take.turns.length} turns · about ${clock(take.seconds)} of audio · ~$${
                    take.cost_usd.toFixed(4)} of speech`;
        }
        if (scope && !turns.length) {
            setStatus(`No audio for ${scopeTitle()} yet. Generate it below.`);
        } else if (!scope && take.scope) {
            setStatus(
                `The latest take covers ${titleFor(take.scope)}. Generate the whole pack to hear every section.`,
            );
        }
    }

    function turnNode(turn) {
        const item = element("li", `turn turn--${turn.role}`);
        item.dataset.turnKind = turn.kind || "";
        const head = element("header", "turn__head");
        const role = element("span", "turn__role");
        const icon = document.createElement("i");
        icon.className = `uil ${turn.role === "interviewer" ? "uil-microphone" : "uil-user"}`;
        role.append(icon, document.createTextNode(turn.role === "interviewer" ? " Interviewer" : " You"));
        head.append(role, element("span", "turn__section", turn.section || ""));
        if (turn.direction?.length) {
            const tones = element("span", "turn__tones");
            turn.direction.forEach((tone) => tones.append(element("span", "turn__tone", tone)));
            head.append(tones);
        }
        const body = element("div", "turn__body");
        (turn.paragraphs?.length ? turn.paragraphs : [turn.text]).forEach((paragraph) => {
            body.append(element("p", "turn__text", paragraph));
        });
        item.append(head, body);
        if (turn.audio_url) {
            const player = element("div", "turn__player");
            player.dataset.player = "";
            const audio = document.createElement("audio");
            audio.className = "turn__audio";
            audio.preload = "metadata";
            audio.src = turn.audio_url;
            const toggle = element("button", "audio-player__toggle");
            toggle.type = "button";
            toggle.dataset.audioToggle = "";
            toggle.setAttribute("aria-label", "Play");
            toggle.innerHTML = '<i class="uil uil-play"></i>';
            const track = element("div", "audio-player__track");
            track.dataset.audioTrack = "";
            track.tabIndex = 0;
            track.setAttribute("role", "slider");
            track.setAttribute("aria-label", "Seek through this turn");
            track.setAttribute("aria-valuemin", "0");
            track.setAttribute("aria-valuemax", "100");
            track.setAttribute("aria-valuenow", "0");
            const fill = element("span", "audio-player__fill");
            fill.dataset.audioFill = "";
            track.append(fill);
            const time = element("span", "audio-player__time");
            time.dataset.audioTime = "";
            time.textContent = "0:00 / 0:00";
            player.append(audio, toggle, track, time);
            item.append(player);
        } else if (turn.error) {
            item.append(element("p", "turn__error", turn.error));
        }
        return item;
    }

    function clock(seconds) {
        const total = Math.floor(Number(seconds) || 0);
        return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
    }

    // -- turn players ------------------------------------------------------
    function bindPlayers(root) {
        root?.querySelectorAll("[data-player]").forEach(bindPlayer);
    }

    function bindPlayer(root) {
        if (root.dataset.bound) return;
        root.dataset.bound = "true";
        const audio = root.querySelector("audio");
        const toggle = root.querySelector("[data-audio-toggle]");
        const track = root.querySelector("[data-audio-track]");
        const fill = root.querySelector("[data-audio-fill]");
        const time = root.querySelector("[data-audio-time]");
        if (!audio || !toggle || !track || !fill || !time) return;
        const icon = toggle.querySelector("i");

        function setPlaying(playing) {
            if (icon) icon.className = `uil ${playing ? "uil-pause" : "uil-play"}`;
            toggle.setAttribute("aria-label", playing ? "Pause" : "Play");
        }

        function render() {
            const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
            const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
            const percent = duration ? Math.min(100, (current / duration) * 100) : 0;
            fill.style.width = `${percent}%`;
            time.textContent = `${clock(current)} / ${clock(duration)}`;
            track.setAttribute("aria-valuenow", String(Math.round(percent)));
        }

        function seek(fraction) {
            if (!Number.isFinite(audio.duration) || !audio.duration) return;
            audio.currentTime = Math.max(0, Math.min(audio.duration, fraction * audio.duration));
            render();
        }

        toggle.addEventListener("click", () => {
            if (audio.paused) {
                audio.play().catch(() => {
                    time.textContent = "Could not play";
                });
            } else {
                audio.pause();
            }
        });
        track.addEventListener("click", (event) => {
            const rect = track.getBoundingClientRect();
            if (!rect.width) return;
            seek((event.clientX - rect.left) / rect.width);
        });
        track.addEventListener("keydown", (event) => {
            if (!Number.isFinite(audio.duration) || !audio.duration) return;
            const step = event.shiftKey ? 10 : 5;
            if (event.key === "ArrowRight" || event.key === "ArrowUp") {
                event.preventDefault();
                audio.currentTime = Math.min(audio.duration, audio.currentTime + step);
            } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
                event.preventDefault();
                audio.currentTime = Math.max(0, audio.currentTime - step);
            } else if (event.key === "Home") {
                event.preventDefault();
                audio.currentTime = 0;
            } else if (event.key === "End") {
                event.preventDefault();
                audio.currentTime = audio.duration;
            }
            render();
        });
        audio.addEventListener("loadedmetadata", render);
        audio.addEventListener("durationchange", render);
        audio.addEventListener("timeupdate", render);
        audio.addEventListener("play", () => {
            document.querySelectorAll("[data-player] audio").forEach((other) => {
                if (other !== audio) other.pause();
            });
            setPlaying(true);
        });
        audio.addEventListener("pause", () => setPlaying(false));
        audio.addEventListener("ended", () => {
            setPlaying(false);
            audio.currentTime = 0;
            render();
        });
        audio.addEventListener("error", () => {
            time.textContent = "Audio unavailable";
        });
        render();
        if (audio.readyState >= 1) render();
    }

    // -- reference recording -----------------------------------------------
    const upload = studio.querySelector("[data-reference-upload]");
    const fileInput = studio.querySelector("[data-reference-file]");
    const fileName = studio.querySelector("[data-reference-name]");
    const referenceNote = studio.querySelector("[data-reference-note]");
    const referenceState = studio.querySelector("[data-reference-state]");

    fileInput?.addEventListener("change", () => {
        if (fileName) fileName.textContent = fileInput.files?.[0]?.name || "No file chosen";
    });

    upload?.addEventListener("click", async () => {
        const file = fileInput?.files?.[0];
        if (!file) {
            if (referenceNote) referenceNote.textContent = "Choose a recording first.";
            return;
        }
        const label = upload.innerHTML;
        upload.disabled = true;
        upload.innerHTML = '<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> Uploading';
        try {
            const data = new FormData();
            data.append("file", file);
            const response = await fetch("/api/voices/reference", {
                method: "POST",
                headers: { "X-CSRF-Token": csrf },
                body: data,
            });
            const body = await response.json().catch(() => ({}));
            const ok = response.ok && body.saved;
            if (referenceNote) referenceNote.textContent = ok
                ? body.note
                : body.error?.message || "That recording could not be saved.";
            if (ok) {
                studio.dataset.reference = "true";
                if (referenceState) referenceState.textContent = body.cloned ? "Reference cloned" : "Reference saved";
            }
        } finally {
            upload.disabled = false;
            upload.innerHTML = label;
        }
    });

    // -- load the catalogue ------------------------------------------------
    fetch("/api/tts/voices")
        .then((response) => (response.ok ? response.json() : Promise.reject(new Error("catalogue"))))
        .then((body) => {
            const genders = [...new Set(body.voices.map((voice) => voice.gender))].filter(
                (gender) => gender && gender !== "unspecified",
            );
            const ethnicities = [...new Set(body.voices.map((voice) => voice.ethnicity))].filter(
                (ethnicity) => ethnicity && ethnicity !== "unspecified",
            );
            Object.values(pickers).forEach((picker) => {
                if (!picker) return;
                picker.voices = body.voices;
                picker.preset = picker.preset || body.defaults?.[picker.root.dataset.picker];
                addOptions(picker.gender, genders, "Any gender");
                addOptions(picker.ethnicity, ethnicities, "Any ethnicity");
                if (!body.voices.length) {
                    picker.preview.replaceChildren(emptyLine("This provider returned no voices."));
                    return;
                }
                fillPicker(picker);
            });
            if (!body.supports_clone) {
                const block = studio.querySelector("[data-reference-upload]");
                if (block) block.disabled = true;
            }
        })
        .catch(() => {
            Object.values(pickers).forEach((picker) => {
                picker?.preview?.replaceChildren(
                    emptyLine("The voice catalogue could not be loaded. Reload the page to try again."),
                );
            });
        });

    function addOptions(select, values, anyLabel) {
        if (!select) return;
        const first = select.querySelector("option");
        select.replaceChildren(...[first].filter(Boolean), ...values.map((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value.charAt(0).toUpperCase() + value.slice(1);
            return option;
        }));
        if (first && !first.value) first.textContent = anyLabel;
    }
})();
