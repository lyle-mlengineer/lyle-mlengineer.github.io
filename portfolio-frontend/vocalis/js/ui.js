/*=============== VOCALIS SHARED UI ===============*/
(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  /*=============== MOBILE MENU ===============*/
  const navMenu = $('#nav-menu');
  const navToggle = $('#nav-toggle');
  const navClose = $('#nav-close');

  const setMenu = (open) => {
    if (!navMenu || !navToggle) return;
    navMenu.classList.toggle('show-menu', open);
    navToggle.setAttribute('aria-expanded', String(open));
  };

  if (navToggle) navToggle.addEventListener('click', () => setMenu(true));
  if (navClose) navClose.addEventListener('click', () => setMenu(false));

  $$('.nav__link').forEach((link) => {
    link.addEventListener('click', () => setMenu(false));
  });

  document.addEventListener('click', (event) => {
    if (!navMenu || !navMenu.classList.contains('show-menu')) return;
    if (navMenu.contains(event.target) || (navToggle && navToggle.contains(event.target))) return;
    setMenu(false);
  });

  /*=============== HEADER STATE ===============*/
  const header = $('#header');

  if (header) {
    const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 16);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /*=============== APP SIDEBAR ===============*/
  const app = $('#app');
  const sidebarClose = $('#sidebarClose');
  const sidebarToggle = $('#sidebarToggle');
  const sidebarScrim = $('#sidebarScrim');

  const setSidebar = (open) => {
    if (!app) return;
    app.classList.toggle('is-menu-open', open);
    if (sidebarScrim) sidebarScrim.hidden = !open;
    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', String(open));
  };

  if (sidebarToggle) sidebarToggle.addEventListener('click', () => setSidebar(true));
  if (sidebarClose) sidebarClose.addEventListener('click', () => setSidebar(false));
  if (sidebarScrim) sidebarScrim.addEventListener('click', () => setSidebar(false));

  $$('.app__link').forEach((link) => {
    link.addEventListener('click', () => setSidebar(false));
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    setMenu(false);
    setSidebar(false);
  });

  /*=============== REVEAL ON SCROLL ===============*/
  const revealItems = $$('.reveal');

  revealItems.forEach((item) => {
    if (!item.parentElement) return;
    const siblings = Array.from(item.parentElement.children).filter((el) => el.classList.contains('reveal'));
    const index = siblings.indexOf(item);
    item.style.transitionDelay = `${Math.min(index, 6) * 70}ms`;
  });

  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.12 }
    );

    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add('is-visible'));
  }

  /*=============== WAVEFORM BARS ===============*/
  const rng = (seed) => {
    let value = seed * 9301 + 49297;
    return () => {
      value = (value * 9301 + 49297) % 233280;
      return value / 233280;
    };
  };

  $$('.waveform').forEach((wave) => {
    const bars = Number(wave.dataset.bars) || 24;
    const heights = wave.dataset.heights
      ? wave.dataset.heights.split(',').map(Number).filter(Number.isFinite)
      : null;
    const seed = Number(wave.dataset.seed) || 11;
    const random = rng(seed);

    for (let i = 0; i < bars; i += 1) {
      const bar = document.createElement('span');
      const burst = Math.pow(Math.abs(Math.sin((i / bars) * Math.PI * 3 + seed * 0.7)), 1.6);
      const height = heights ? heights[i % heights.length] : 16 + burst * 52 + random() * 30;
      bar.style.setProperty('--h', Math.max(14, Math.min(98, Math.round(height))));
      bar.style.setProperty('--dur', `${(0.55 + random() * 0.85).toFixed(2)}s`);
      bar.style.setProperty('--delay', `${(random() * 0.55).toFixed(2)}s`);
      wave.appendChild(bar);
    }
  });

  /*=============== TOASTS ===============*/
  const toast = (message) => {
    const host = $('#toastHost');
    if (!host || !message) return;

    while (host.children.length >= 3) host.firstElementChild.remove();

    const toastEl = document.createElement('div');
    toastEl.className = 'toast';
    toastEl.textContent = message;
    host.appendChild(toastEl);

    requestAnimationFrame(() => toastEl.classList.add('is-in'));

    window.setTimeout(() => {
      toastEl.classList.remove('is-in');
      toastEl.classList.add('is-out');
      window.setTimeout(() => toastEl.remove(), 320);
    }, 3200);
  };

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-toast]');
    if (!trigger) return;
    if (trigger.tagName === 'A') event.preventDefault();
    toast(trigger.dataset.toast);
  });

  /*=============== SPEECH ENGINE ===============*/
  const synth = window.speechSynthesis || null;
  const speechSupported = Boolean(synth) && 'SpeechSynthesisUtterance' in window;

  let systemVoices = [];
  let activeSpeech = null;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const refreshVoices = () => {
    if (!synth) return;
    const loaded = synth.getVoices();
    if (loaded && loaded.length) systemVoices = loaded;
  };

  const findVoice = (lang = 'en-US') => {
    if (!systemVoices.length) return null;
    const target = (lang || 'en-US').toLowerCase();
    const prefix = target.slice(0, 2);

    return (
      systemVoices.find((voice) => voice.lang.toLowerCase().replace('_', '-') === target) ||
      systemVoices.find((voice) => voice.lang.toLowerCase().replace('_', '-').startsWith(target)) ||
      systemVoices.find((voice) => voice.lang.toLowerCase().startsWith(prefix)) ||
      systemVoices.find((voice) => voice.lang.toLowerCase().startsWith('en')) ||
      systemVoices[0]
    );
  };

  const stop = () => {
    if (!activeSpeech) return;
    const session = activeSpeech;
    activeSpeech = null;
    if (synth) {
      try {
        synth.cancel();
      } catch (error) {
        /* some browsers throw when the queue is already empty */
      }
    }
    session.finish('canceled');
  };

  /**
   * Speaks one line and reports lifecycle states: end, canceled, error, unsupported.
   * Always cancels whatever was speaking before.
   */
  const speak = ({ text, lang = 'en-US', pitch = 1, rate = 1, onStart, onEnd }) => {
    if (!speechSupported || !text) {
      if (onEnd) onEnd('unsupported');
      return false;
    }

    stop();

    const utterance = new SpeechSynthesisUtterance(text);
    const voice = findVoice(lang);
    if (voice) utterance.voice = voice;
    utterance.lang = (voice && voice.lang) || lang || 'en-US';
    utterance.pitch = clamp(Number(pitch) || 1, 0.1, 2);
    utterance.rate = clamp(Number(rate) || 1, 0.4, 2);

    let settled = false;

    const finish = (state) => {
      if (settled) return;
      settled = true;
      if (activeSpeech && activeSpeech.utterance === utterance) activeSpeech = null;
      if (onEnd) onEnd(state);
    };

    utterance.onend = () => finish('end');
    utterance.onerror = (event) => finish(event && event.error === 'canceled' ? 'canceled' : 'error');

    activeSpeech = { utterance, finish };

    if (onStart) onStart();

    try {
      synth.speak(utterance);
    } catch (error) {
      finish('error');
      return false;
    }

    return true;
  };

  if (speechSupported) {
    refreshVoices();
    if (typeof synth.addEventListener === 'function') {
      synth.addEventListener('voiceschanged', refreshVoices);
    }
    window.setTimeout(refreshVoices, 400);
  }

  window.Vocalis = {
    speechSupported,
    speak,
    stopSpeech: stop,
    toast,
  };
})();
