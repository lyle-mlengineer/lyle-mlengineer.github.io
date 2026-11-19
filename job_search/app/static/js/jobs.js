/* Jobs list: resume a stopped run without opening the job. */
(function () {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const buttons = document.querySelectorAll("[data-resume-job]");
    if (!buttons.length) return;

    buttons.forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();
            const jobId = button.dataset.resumeJob;
            const label = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<i class="uil uil-spinner-alt"></i> Resuming';

            try {
                const response = await fetch(`/api/jobs/${jobId}/resume`, {
                    method: "POST",
                    headers: { "X-CSRF-Token": csrf },
                });
                if (response.status === 202) {
                    window.location.href = `/jobs/${jobId}`;
                    return;
                }
                // Anything else (already running, already finished) is explained
                // on the job page, so send the user there instead of failing here.
                window.location.href = `/jobs/${jobId}`;
            } catch (error) {
                button.disabled = false;
                button.innerHTML = label;
                window.location.href = `/jobs/${jobId}`;
            }
        });
    });
})();
