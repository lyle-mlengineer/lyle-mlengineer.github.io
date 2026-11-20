/* Jobs list: resume a stopped run, or delete a job, without opening it. */
(function () {
    const resumeButtons = document.querySelectorAll("[data-resume-job]");
    const deleteButtons = document.querySelectorAll("[data-delete-job]");
    if (!resumeButtons.length && !deleteButtons.length) return;

    resumeButtons.forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();
            const jobId = button.dataset.resumeJob;
            const label = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<i class="uil uil-spinner-alt"></i> Resuming';

            const result = await window.Skipper.resumeJob(jobId);
            if (result.ok || result.status !== 0) {
                // A refusal is explained on the job page; a network failure keeps
                // the row usable instead of navigating into a dead end.
                window.location.href = `/jobs/${jobId}`;
                return;
            }
            button.disabled = false;
            button.innerHTML = label;
        });
    });

    deleteButtons.forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.preventDefault();
            event.stopPropagation();
            const jobId = button.dataset.deleteJob;
            if (!window.confirm("Delete this job and everything generated for it? This cannot be undone.")) {
                return;
            }
            const label = button.innerHTML;
            button.disabled = true;
            button.innerHTML = '<i class="uil uil-spinner-alt"></i>';
            const result = await window.Skipper.deleteJob(jobId);
            if (result.ok) {
                button.closest(".list__row")?.remove();
                if (!document.querySelectorAll(".list__row").length) window.location.reload();
                return;
            }
            button.disabled = false;
            button.innerHTML = label;
            window.alert(result.message || "That job could not be deleted.");
        });
    });
})();
