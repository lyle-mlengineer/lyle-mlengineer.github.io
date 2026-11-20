/* System design brief: write one subcomponent per request, on demand. */
(function () {
    const doc = document.querySelector('[data-interview-kind="system_design"]');
    const prose = doc?.querySelector(".prose");
    if (!doc || !prose) return;

    const jobId = window.location.pathname.split("/").filter(Boolean).pop();
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const sections = [
        "requirements",
        "entities",
        "api",
        "data_flow",
        "high_level",
        "deep_dives",
        "questions",
    ];
    const labels = {
        requirements: "requirements",
        entities: "core entities",
        api: "API design",
        data_flow: "data flow",
        high_level: "high-level design",
        deep_dives: "deep dives",
        questions: "interviewer questions",
        follow_ups: "follow-ups",
    };
    const headings = {
        requirements: ["Requirements"],
        entities: ["Core entities"],
        api: ["API design"],
        data_flow: ["Data flow"],
        high_level: ["High-level design", "Diagram"],
        deep_dives: ["Deep dives", "Trade-offs"],
        questions: [
            "Questions the interviewer may ask",
            "Questions to ask the interviewer",
        ],
        follow_ups: ["Follow-ups"],
    };
    const active = new Set();
    const revealed = new Map();

    function questionDetails(index) {
        const title = [...prose.querySelectorAll("h3")].find((heading) =>
            heading.textContent.trim().startsWith(`${index}.`)
        );
        if (!title) return [];
        const found = [];
        let node = title.nextElementSibling;
        while (node && node.tagName !== "H3") {
            if (node.matches("details.design-section")) found.push(node);
            node = node.nextElementSibling;
        }
        return found;
    }

    function rememberOpen(index) {
        const open = revealed.get(index) || new Set();
        questionDetails(index).forEach((details) => {
            if (!details.open) return;
            const title = details.querySelector("summary")?.textContent.trim();
            if (title) open.add(title);
        });
        revealed.set(index, open);
    }

    function reveal(index, section) {
        const open = revealed.get(index) || new Set();
        (headings[section] || []).forEach((title) => open.add(title));
        revealed.set(index, open);
        questionDetails(index).forEach((details) => {
            const title = details.querySelector("summary")?.textContent.trim();
            if (title && open.has(title)) details.open = true;
        });
    }

    async function writeSection(index, section) {
        const response = await fetch(
            `/api/jobs/${jobId}/system-design/${index}/section`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrf,
                },
                body: JSON.stringify({ section }),
            }
        );
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = {};
        }
        if (!response.ok) {
            const message = data?.error?.message || `HTTP ${response.status}`;
            throw new Error(message);
        }
        return data;
    }

    async function loadDesign(index, button) {
        if (active.has(index)) return;
        active.add(index);
        button.disabled = true;
        try {
            for (const section of sections) {
                button.textContent = `Writing ${labels[section]}…`;
                const data = await writeSection(index, section);
                rememberOpen(index);
                prose.innerHTML = data.html;
                reveal(index, section);
                button = prose.querySelector(`[data-design-load="${index}"]`);
                if (!button) return;
            }
        } catch (error) {
            button.textContent = `Try again — ${error.message}`;
            button.disabled = false;
        } finally {
            active.delete(index);
        }
    }

    prose.addEventListener("click", (event) => {
        const button = event.target.closest("[data-design-load]");
        if (!button) return;
        loadDesign(Number(button.dataset.designLoad), button);
    });

    prose.addEventListener(
        "toggle",
        async (event) => {
            const details = event.target.closest("[data-design-followups]");
            if (!details || !details.open || details.dataset.loading) return;
            details.dataset.loading = "1";
            const index = Number(details.dataset.designFollowups);
            const note = details.querySelector("p");
            if (note) note.textContent = "Writing follow-up questions…";
            try {
                const data = await writeSection(index, "follow_ups");
                rememberOpen(index);
                prose.innerHTML = data.html;
                reveal(index, "follow_ups");
            } catch (error) {
                if (note) note.textContent = `Could not write follow-ups — ${error.message}`;
                delete details.dataset.loading;
            }
        },
        true
    );
})();
