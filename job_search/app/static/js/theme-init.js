/* Applies the stored theme before first paint so the page never flashes. */
(function () {
    try {
        var stored = localStorage.getItem('skipper-theme');
        if (stored === 'dark') {
            document.body.classList.add('dark-theme');
        }
    } catch (error) {
        /* private mode: fall back to the light theme */
    }
})();
