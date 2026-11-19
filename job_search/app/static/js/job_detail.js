/* Job page: live run panel, cancel and retry. */
(function () {
    const panel = document.getElementById("run-panel");
    if (!panel) return;

    const runId = panel.dataset.runId;
    const initialStatus = panel.dataset.runStatus;
    const jobId = window.location.pathname.split("/").filter(Boolean).pop();
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const active = initialStatus === "queued" || initialStatus === "running";

    const bar = document.getElementById("run-bar");
    const progress = document.getElementById("run-progress");
    const hint = document.getElementById("run-hint");
    const errorBox = document.getElementById("run-error");
    const steps = document.getElementById("run-steps");
    const cancel = document.getElementById("run-cancel");
    const retry = document.getElementById("run-retry");

    function update(data) {
        if (bar) bar.style.width = `${data.progress_pct || 0}%`;
        if (progress) progress.setAttribute("aria-valuenow", String(data.progress_pct || 0));
        if (hint && data.current_step) {
            hint.textContent = `Working on ${data.current_step.replaceAll("_", " ")} — ${data.progress_pct}%`;
        }
        if (errorBox) {
            errorBox.textContent = data.error || "";
            errorBox.hidden = !data.error;
        }
        const bySkill = Object.fromEntries((data.steps || []).map((step) => [step.skill, step]));
        steps?.querySelectorAll("[data-skill]").forEach((row) => {
            const step = bySkill[row.dataset.skill];
            if (!step) return;
            row.classList.remove("steps__item--pending", "steps__item--running", "steps__item--succeeded", "steps__item--failed", "steps__item--skipped");
            row.classList.add(`steps__item--${step.status}`);
            const meta = row.querySelector(".steps__meta");
            if (meta) {
                const parts = [];
                if (step.duration_ms) parts.push(`${step.duration_ms} ms`);
                if (step.tokens_in || step.tokens_out) parts.push(`${step.tokens_in + step.tokens_out} tokens`);
                meta.textContent = parts.join(" · ");
            }
        });
    }

    if (active && runId) {
        window.pollRun(runId, {
            onUpdate: update,
            onDone: () => window.location.reload(),
            onGiveUp: () => {
                if (hint) hint.textContent = "Lost contact with the server — refresh to check again.";
            },
        });
    }

    cancel?.addEventListener("click", async () => {
        cancel.disabled = true;
        cancel.textContent = "Cancelling…";
        try {
            const response = await fetch(`/api/runs/${runId}/cancel`, {
                method: "POST",
                headers: { "X-CSRF-Token": csrf },
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
        } catch (error) {
            if (hint) hint.textContent = "Could not cancel — refresh and try again.";
            cancel.disabled = false;
            cancel.textContent = "Cancel";
        }
    });

    retry?.addEventListener("click", async () => {
        retry.disabled = true;
        const original = retry.innerHTML;
        retry.innerHTML = '<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> Starting…';
        try {
            const response = await fetch(`/api/jobs/${jobId}/runs`, {
                method: "POST",
                headers: { "X-CSRF-Token": csrf },
            });
            if (response.status === 202) {
                window.location.reload();
                return;
            }
            const body = await response.json().catch(() => ({}));
            if (errorBox) {
                errorBox.textContent = body.error?.message || "The run could not be started.";
                errorBox.hidden = false;
            }
        } catch (error) {
            if (errorBox) {
                errorBox.textContent = "Lost contact with the server. Try again.";
                errorBox.hidden = false;
            }
        } finally {
            retry.disabled = false;
            retry.innerHTML = original;
        }
    });
})();
