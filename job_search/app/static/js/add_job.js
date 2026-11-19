/* Add-job dialog: one posting, pasted text, or a whole careers page. */
(function () {
    const dialog = document.getElementById("add-job");
    if (!dialog) return;

    const form = document.getElementById("add-job-form");
    const errorBox = document.getElementById("add-job-error");
    const submit = document.getElementById("add-job-submit");
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const urlInput = form.querySelector('[name="source_url"]');
    const textInput = form.querySelector('[name="source_text"]');
    const tabs = dialog.querySelector(".tabs");
    const panels = dialog.querySelectorAll("[data-panel]");
    const discovery = document.getElementById("discovery-results");
    const discoveryList = document.getElementById("discovery-list");
    const discoverySummary = document.getElementById("discovery-summary");
    const discoveryAdd = document.getElementById("discovery-add");
    const discoveryBack = document.getElementById("discovery-back");
    let mode = "url";
    let found = [];

    function showError(message) {
        errorBox.textContent = message;
        errorBox.hidden = false;
    }

    function clearError() {
        errorBox.hidden = true;
        errorBox.textContent = "";
    }

    function resetDiscovery() {
        found = [];
        discovery.hidden = true;
        discoveryList.textContent = "";
        tabs.hidden = false;
        submit.hidden = false;
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.panel !== mode;
        });
    }

    function open() {
        clearError();
        resetDiscovery();
        dialog.showModal();
        (mode === "url" ? urlInput : textInput).focus();
    }

    function close() {
        if (dialog.open) dialog.close();
    }

    function showDiscovery(body) {
        found = body.postings || [];
        tabs.hidden = true;
        panels.forEach((panel) => { panel.hidden = true; });
        submit.hidden = true;
        discovery.hidden = false;
        discoverySummary.textContent = `${body.count} role${body.count === 1 ? "" : "s"} matched ${body.roles?.join(", ") || "your targets"}. Uncheck anything you do not want.`;
        discoveryList.textContent = "";
        found.forEach((posting, index) => {
            const row = document.createElement("li");
            row.className = "discovery__item";
            const label = document.createElement("label");
            label.className = "discovery__label";
            const box = document.createElement("input");
            box.type = "checkbox";
            box.checked = true;
            box.value = posting.url;
            box.id = `discovery-job-${index}`;
            const text = document.createElement("span");
            const title = document.createElement("span");
            title.className = "discovery__title";
            title.textContent = posting.title;
            const meta = document.createElement("span");
            meta.className = "discovery__meta";
            meta.textContent = [posting.company, posting.location].filter(Boolean).join(" · ") || "Location not listed";
            text.append(title, meta);
            label.append(box, text);
            row.append(label);
            discoveryList.append(row);
        });
        discoveryAdd.focus();
    }

    function selectedUrls() {
        return Array.from(discoveryList.querySelectorAll('input[type="checkbox"]:checked')).map((box) => box.value);
    }

    document.querySelectorAll("[data-add-job-open]").forEach((button) => {
        button.addEventListener("click", open);
    });
    document.querySelectorAll("[data-add-job-close]").forEach((button) => {
        button.addEventListener("click", close);
    });

    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) close();
    });
    dialog.addEventListener("close", resetDiscovery);

    discoveryBack.addEventListener("click", () => {
        resetDiscovery();
        urlInput.focus();
    });

    dialog.querySelectorAll("[data-tab]").forEach((tab) => {
        tab.addEventListener("click", () => {
            mode = tab.dataset.tab;
            dialog.querySelectorAll("[data-tab]").forEach((other) => {
                const active = other === tab;
                other.classList.toggle("tabs__tab--active", active);
                other.setAttribute("aria-selected", String(active));
            });
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.panel !== mode;
            });
            (mode === "url" ? urlInput : textInput).focus();
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearError();

        const payload = mode === "url"
            ? { source_url: urlInput.value.trim() }
            : { source_text: textInput.value.trim() };

        if (mode === "url" && !payload.source_url) {
            showError("Paste the posting or careers-page link first.");
            return;
        }
        if (mode === "text" && payload.source_text.length < 200) {
            showError("That looks too short for a job description. Paste the whole posting.");
            return;
        }

        submit.disabled = true;
        submit.classList.add("is-loading");
        const original = submit.innerHTML;
        submit.innerHTML = '<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> Reading…';

        try {
            const response = await fetch("/api/jobs", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
                body: JSON.stringify(payload),
            });
            const body = await response.json().catch(() => ({}));

            if (response.ok && Array.isArray(body.postings) && body.postings.length) {
                showDiscovery(body);
                return;
            }
            if (response.status === 202 && body.job_id) {
                window.location.assign(body.job_url || `/jobs/${body.job_id}`);
                return;
            }
            if (response.status === 409 && body.error?.details?.job_id) {
                window.location.assign(body.error.details.job_url || `/jobs/${body.error.details.job_id}`);
                return;
            }
            showError(body.error?.message || "That job could not be added.");
        } catch (error) {
            showError("Lost contact with the server. Check the connection and try again.");
        } finally {
            submit.disabled = false;
            submit.classList.remove("is-loading");
            submit.innerHTML = original;
        }
    });

    discoveryAdd.addEventListener("click", async () => {
        clearError();
        const items = selectedUrls();
        if (!items.length) {
            showError("Select at least one role to add.");
            return;
        }
        discoveryAdd.disabled = true;
        const original = discoveryAdd.innerHTML;
        discoveryAdd.innerHTML = '<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> Adding…';
        try {
            const response = await fetch("/api/jobs/bulk", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
                body: JSON.stringify({ items: items.map((url) => ({ url })) }),
            });
            const body = await response.json().catch(() => ({}));
            if (response.status === 202) {
                window.location.assign("/jobs");
                return;
            }
            showError(body.error?.message || "Those jobs could not be added.");
        } catch (error) {
            showError("Lost contact with the server. Try again.");
        } finally {
            discoveryAdd.disabled = false;
            discoveryAdd.innerHTML = original;
        }
    });
})();
