/* pollRun — one poller for the whole app.
   Interval starts at 1.5 s, backs off to 2 s after 30 s and 5 s after 3 min,
   pauses while the tab is hidden, and gives up after five consecutive failures
   instead of spinning forever. */
(function () {
    const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

    function pollRun(runId, options) {
        const { onUpdate, onDone, onError, onGiveUp } = options || {};
        let failures = 0;
        let timer = null;
        let stopped = false;
        const startedAt = Date.now();

        function interval() {
            const elapsed = Date.now() - startedAt;
            if (elapsed > 180000) return 5000;
            if (elapsed > 30000) return 2000;
            return 1500;
        }

        async function tick() {
            if (stopped) return;
            if (document.hidden) {
                schedule();
                return;
            }
            try {
                const response = await fetch(`/api/runs/${runId}`, {
                    headers: { Accept: "application/json" },
                    cache: "no-store",
                });
                if (response.status === 401) {
                    stopped = true;
                    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
                    return;
                }
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                failures = 0;
                if (onUpdate) onUpdate(data);
                if (TERMINAL.has(data.status)) {
                    stopped = true;
                    if (onDone) onDone(data);
                    return;
                }
            } catch (error) {
                failures += 1;
                if (failures >= 5) {
                    stopped = true;
                    if (onGiveUp) onGiveUp();
                    return;
                }
                if (onError) onError(error);
            }
            schedule();
        }

        function schedule() {
            if (stopped) return;
            clearTimeout(timer);
            timer = setTimeout(tick, interval());
        }

        document.addEventListener("visibilitychange", () => {
            if (!document.hidden && !stopped) {
                clearTimeout(timer);
                tick();
            }
        });

        window.addEventListener("beforeunload", () => {
            stopped = true;
            clearTimeout(timer);
        });

        tick();

        return {
            stop() {
                stopped = true;
                clearTimeout(timer);
            },
        };
    }

    window.pollRun = pollRun;
})();
