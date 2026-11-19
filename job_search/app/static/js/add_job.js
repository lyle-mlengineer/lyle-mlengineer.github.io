/* Add-job dialog: submit a link or pasted text, then hand over to the job page
   where polling takes over. No framework, no build step. */
(function () {
    const dialog = document.getElementById("add-job");
    if (!dialog) return;

    const form = document.getElementById("add-job-form");
    const errorBox = document.getElementById("add-job-error");
    const submit = document.getElementById("add-job-submit");
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const urlInput = form.querySelector('[name="source_url"]');
    const textInput = form.querySelector('[name="source_text"]');
    let mode = "url";

    function showError(message) {
        errorBox.textContent = message;
        errorBox.hidden = false;
    }

    function clearError() {
        errorBox.hidden = true;
        errorBox.textContent = "";
    }

    function open() {
        clearError();
        dialog.showModal();
        (mode === "url" ? urlInput : textInput).focus();
    }

    function close() {
        if (dialog.open) dialog.close();
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

    dialog.querySelectorAll("[data-tab]").forEach((tab) => {
        tab.addEventListener("click", () => {
            mode = tab.dataset.tab;
            dialog.querySelectorAll("[data-tab]").forEach((other) => {
                const active = other === tab;
                other.classList.toggle("tabs__tab--active", active);
                other.setAttribute("aria-selected", String(active));
            });
            dialog.querySelectorAll("[data-panel]").forEach((panel) => {
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
            showError("Paste the posting link first.");
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
})();
