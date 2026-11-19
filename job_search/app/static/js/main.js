/* Skipper UI — no dependencies, no build step.
   Everything here is progressive: the pages work before this file runs. */

(function () {
    'use strict';

    /* ---------------- theme ---------------- */
    var themeButton = document.getElementById('theme-button');
    if (themeButton) {
        themeButton.setAttribute('role', 'button');
        themeButton.setAttribute('tabindex', '0');
        themeButton.setAttribute('aria-label', 'Toggle dark theme');
        themeButton.addEventListener('click', toggleTheme);
        themeButton.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleTheme();
            }
        });
    }

    function toggleTheme() {
        var isDark = document.body.classList.toggle('dark-theme');
        themeButton.classList.toggle('uil-sun', isDark);
        themeButton.classList.toggle('uil-moon', !isDark);
        try {
            localStorage.setItem('skipper-theme', isDark ? 'dark' : 'light');
        } catch (error) {
            /* ignore */
        }
    }

    /* ---------------- mobile nav ---------------- */
    var navMenu = document.getElementById('nav-menu');
    var navToggle = document.getElementById('nav-toggle');
    var navClose = document.getElementById('nav-close');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function () {
            navMenu.classList.add('show-menu');
        });
    }
    if (navClose && navMenu) {
        navClose.addEventListener('click', function () {
            navMenu.classList.remove('show-menu');
        });
    }
    Array.prototype.forEach.call(document.querySelectorAll('.nav__link'), function (link) {
        link.addEventListener('click', function () {
            if (navMenu) navMenu.classList.remove('show-menu');
        });
    });

    /* ---------------- header shadow ---------------- */
    var header = document.getElementById('header');
    function onScroll() {
        if (header) header.classList.toggle('scroll-header', window.scrollY >= 80);
        var scrollUp = document.getElementById('scroll-up');
        if (scrollUp) scrollUp.classList.toggle('show-scroll', window.scrollY >= 560);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    /* ---------------- active section link ---------------- */
    var sections = document.querySelectorAll('section[id]');
    var navLinks = document.querySelectorAll('.nav__link');
    if (sections.length && navLinks.length) {
        function setActive() {
            var fromTop = window.scrollY + 120;
            Array.prototype.forEach.call(sections, function (section) {
                var id = section.getAttribute('id');
                var offset = section.offsetTop;
                var height = section.offsetHeight;
                if (fromTop >= offset && fromTop < offset + height) {
                    Array.prototype.forEach.call(navLinks, function (link) {
                        link.classList.toggle('active-link', link.getAttribute('href') === '#' + id);
                    });
                }
            });
        }
        window.addEventListener('scroll', setActive, { passive: true });
        setActive();
    }

    /* ---------------- skills accordion ---------------- */
    var skillCards = Array.prototype.slice.call(document.querySelectorAll('.skills__content'));
    var skillHeaders = document.querySelectorAll('.skills__header');

    function syncSkillAria() {
        skillCards.forEach(function (card) {
            var header = card.querySelector('.skills__header');
            if (header) {
                header.setAttribute('aria-expanded', card.classList.contains('skills__open') ? 'true' : 'false');
            }
        });
    }

    Array.prototype.forEach.call(skillHeaders, function (skillHeader) {
        function toggleSkills() {
            var card = skillHeader.parentNode;
            var wasOpen = card.classList.contains('skills__open');
            skillCards.forEach(function (other) {
                other.classList.remove('skills__open');
                other.classList.add('skills__close');
            });
            if (!wasOpen) {
                card.classList.remove('skills__close');
                card.classList.add('skills__open');
            }
            syncSkillAria();
        }
        skillHeader.addEventListener('click', toggleSkills);
        skillHeader.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleSkills();
            }
        });
    });
    syncSkillAria();

    /* ---------------- CV picker ---------------- */
    var cvMenu = document.querySelector('[data-cv-menu]');
    if (cvMenu) {
        var cvToggle = cvMenu.querySelector('.cv-menu__toggle');
        var cvList = cvMenu.querySelector('.cv-menu__list');
        var cvItems = Array.prototype.slice.call(cvList.querySelectorAll('[role="menuitem"]'));

        function setCvOpen(open) {
            cvToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            cvList.hidden = !open;
        }

        cvToggle.addEventListener('click', function () {
            setCvOpen(cvList.hidden);
        });

        document.addEventListener('click', function (event) {
            if (!cvMenu.contains(event.target)) setCvOpen(false);
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !cvList.hidden) {
                setCvOpen(false);
                cvToggle.focus();
            }
        });

        cvList.addEventListener('keydown', function (event) {
            var index = cvItems.indexOf(document.activeElement);
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                (cvItems[index + 1] || cvItems[0]).focus();
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                (cvItems[index - 1] || cvItems[cvItems.length - 1]).focus();
            } else if (event.key === 'Home') {
                event.preventDefault();
                cvItems[0].focus();
            } else if (event.key === 'End') {
                event.preventDefault();
                cvItems[cvItems.length - 1].focus();
            }
        });
    }

    /* ---------------- copy buttons ---------------- */
    Array.prototype.forEach.call(document.querySelectorAll('[data-copy]'), function (button) {
        button.addEventListener('click', function () {
            var target = document.querySelector(button.getAttribute('data-copy'));
            if (!target) return;
            var text = target.innerText || target.textContent || '';
            var done = function () {
                var original = button.innerHTML;
                button.innerHTML = '<i class="uil uil-check"></i> Copied';
                window.setTimeout(function () { button.innerHTML = original; }, 1800);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(done).catch(function () {});
            }
        });
    });
})();
