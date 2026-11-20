/* Collapsible job-page panels: pipeline, resources, artifacts, research,
   brief and structured fields. The state is remembered per panel so a reload
   does not reopen everything the reader closed. */
(function () {
    'use strict';

    const panels = document.querySelectorAll('[data-collapsible]');
    if (!panels.length) return;

    const storageKey = (panel) => `skipper:collapsed:${panel.id || panel.dataset.collapsible}`;

    panels.forEach((panel) => {
        const head = panel.querySelector('.panel__head');
        if (!head) return;

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'panel__collapse';
        button.setAttribute('aria-expanded', 'true');
        button.innerHTML = '<i class="uil uil-angle-up" aria-hidden="true"></i><span class="visually-hidden">Collapse section</span>';

        const actions = head.querySelector('.panel__actions');
        (actions || head).append(button);
        panel.classList.add('panel--collapsible');

        const setCollapsed = (collapsed) => {
            panel.classList.toggle('is-collapsed', collapsed);
            button.setAttribute('aria-expanded', String(!collapsed));
            button.querySelector('.visually-hidden').textContent = collapsed ? 'Expand section' : 'Collapse section';
            button.querySelector('i').className = collapsed ? 'uil uil-angle-down' : 'uil uil-angle-up';
        };

        let saved = null;
        try {
            saved = window.localStorage.getItem(storageKey(panel));
        } catch (error) {
            /* private mode: no persistence, collapsing still works */
        }
        setCollapsed(saved === '1');

        button.addEventListener('click', () => {
            const collapsed = !panel.classList.contains('is-collapsed');
            setCollapsed(collapsed);
            try {
                window.localStorage.setItem(storageKey(panel), collapsed ? '1' : '0');
            } catch (error) {
                /* ignore storage failures */
            }
        });
    });
})();
