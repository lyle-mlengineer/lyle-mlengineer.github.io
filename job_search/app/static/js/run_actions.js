/* Shared run actions: one place that posts to the job API and normalises the
   result, so buttons on any page behave the same way.

   Every helper resolves to { ok, status, message }. ok is true only for the
   202 the API returns when a run was queued; message is the server's own
   explanation for anything else, ready to show to the user. */
(function () {
    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || "";
    }

    async function post(url, payload) {
        const headers = { "X-CSRF-Token": csrfToken() };
        if (payload) headers["Content-Type"] = "application/json";
        try {
            const response = await fetch(url, {
                method: "POST",
                headers,
                body: payload ? JSON.stringify(payload) : undefined,
            });
            const body = await response.json().catch(() => ({}));
            return {
                ok: response.status === 202,
                status: response.status,
                message: body?.error?.message || "",
                body,
            };
        } catch (error) {
            return { ok: false, status: 0, message: "", body: {} };
        }
    }

    function resumeJob(jobId) {
        return post(`/api/jobs/${jobId}/resume`);
    }

    function runJob(jobId) {
        return post(`/api/jobs/${jobId}/runs`);
    }

    function regenerateArtifact(jobId, skill) {
        return post(`/api/jobs/${jobId}/regenerate`, { skill });
    }

    function fillMissing(jobId) {
        return post(`/api/jobs/${jobId}/backfill`);
    }

    async function deleteJob(jobId) {
        try {
            const response = await fetch(`/api/jobs/${jobId}`, {
                method: "DELETE",
                headers: { "X-CSRF-Token": csrfToken() },
            });
            const body = await response.json().catch(() => ({}));
            return {
                ok: response.ok,
                status: response.status,
                message: body?.error?.message || "",
                body,
            };
        } catch (error) {
            return { ok: false, status: 0, message: "", body: {} };
        }
    }

    window.Skipper = Object.assign(window.Skipper || {}, {
        resumeJob,
        runJob,
        regenerateArtifact,
        fillMissing,
        deleteJob,
    });
})();
