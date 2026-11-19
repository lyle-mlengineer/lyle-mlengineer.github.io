/* Jobs list: resume a stopped run without opening the job. */
(function () {
    const buttons = document.querySelectorAll("[data-resume-job]");
    if (!buttons.length) return;

    buttons.forEach((button) => {
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
})();
