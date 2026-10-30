/*=============== MOBILE MENU ===============*/
const navMenu = document.getElementById('nav-menu');
const navToggle = document.getElementById('nav-toggle');
const navClose = document.getElementById('nav-close');
const navLinks = document.querySelectorAll('.nav__link');

const openMenu = () => {
  navMenu.classList.add('show-menu');
  navToggle.setAttribute('aria-expanded', 'true');
};

const closeMenu = () => {
  navMenu.classList.remove('show-menu');
  navToggle.setAttribute('aria-expanded', 'false');
};

if (navToggle) navToggle.addEventListener('click', openMenu);
if (navClose) navClose.addEventListener('click', closeMenu);

navLinks.forEach((link) => {
  link.addEventListener('click', () => {
    closeMenu();
    navLinks.forEach((n) => n.classList.remove('active-link'));
    link.classList.add('active-link');
  });
});

document.addEventListener('click', (event) => {
  if (!navMenu.classList.contains('show-menu')) return;
  if (navMenu.contains(event.target) || navToggle.contains(event.target)) return;
  closeMenu();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeMenu();
});

/*=============== HEADER STATE ===============*/
const header = document.getElementById('header');
const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 16);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

/*=============== SCROLL SPY ===============*/
const spyLinks = document.querySelectorAll('.nav__link[data-section]');
const spySections = [...spyLinks]
  .map((link) => document.getElementById(link.dataset.section))
  .filter(Boolean);

const spyObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      spyLinks.forEach((link) => {
        link.classList.toggle('active-link', link.dataset.section === entry.target.id);
      });
    });
  },
  { rootMargin: '-40% 0px -55% 0px', threshold: 0 }
);

spySections.forEach((section) => spyObserver.observe(section));

/*=============== REVEAL ON SCROLL ===============*/
const revealItems = document.querySelectorAll('.reveal');

revealItems.forEach((item) => {
  const siblings = [...item.parentElement.children].filter((el) => el.classList.contains('reveal'));
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

document.querySelectorAll('.waveform').forEach((wave) => {
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

/*=============== SPEECH ENGINE ===============*/
const synth = window.speechSynthesis;
const speechSupported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
let browserVoices = [];
let activeSpeech = null;

const cleanVoiceName = (name) =>
  name
    .replace(/^Microsoft\s+/i, '')
    .replace(/^Google\s+/i, '')
    .split(' - ')[0]
    .replace(/\s*\(.*\)$/, '')
    .trim();

const loadVoices = () => {
  if (!speechSupported) return;
  browserVoices = synth.getVoices();
  buildVoiceSelect();
};

const findVoice = (lang) => {
  if (!browserVoices.length) return null;
  const prefix = (lang || 'en-US').slice(0, 2).toLowerCase();
  return (
    browserVoices.find((voice) => voice.lang.replace('_', '-') === lang) ||
    browserVoices.find((voice) => voice.lang.toLowerCase().startsWith(lang ? lang.slice(0, 2).toLowerCase() : 'en')) ||
    browserVoices.find((voice) => voice.lang.toLowerCase().startsWith(prefix)) ||
    browserVoices[0]
  );
};

const stopSpeech = () => {
  if (!activeSpeech) return;
  const session = activeSpeech;
  activeSpeech = null;
  if (synth) synth.cancel();
  session.reset();
};

/**
 * Speaks a line and reports lifecycle back to the caller.
 * Returns false when nothing could be spoken.
 */
const speak = ({ text, voice, lang, pitch = 1, rate = 1, onStart, onEnd }) => {
  if (!speechSupported) {
    if (onEnd) onEnd('unsupported');
    return false;
  }

  stopSpeech();

  const utterance = new SpeechSynthesisUtterance(text);
  const chosen = voice || findVoice(lang || 'en-US');
  if (chosen) utterance.voice = chosen;
  utterance.lang = (chosen && chosen.lang) || lang || 'en-US';
  utterance.pitch = Math.min(2, Math.max(0.1, pitch));
  utterance.rate = Math.min(2, Math.max(0.4, rate));

  let settled = false;

  const finish = (state) => {
    if (settled) return;
    settled = true;
    if (activeSpeech && activeSpeech.utterance === utterance) activeSpeech = null;
    if (onEnd) onEnd(state);
  };

  utterance.onend = () => finish('end');
  utterance.onerror = (event) => finish(event.error === 'canceled' ? 'canceled' : 'error');

  activeSpeech = {
    utterance,
    reset: () => finish('canceled'),
  };

  if (onStart) onStart();
  synth.speak(utterance);
  return true;
};

/*=============== HERO SAMPLE ===============*/
const heroCard = document.getElementById('heroCard');
const heroCardWave = heroCard.querySelector('.waveform');
const heroCardPlay = document.getElementById('heroCardPlay');
const heroPlay = document.getElementById('heroPlay');

const HERO_LINE =
  "Hi — I'm Aria. This is a human voice designed by Vocalis: warm, unhurried, and never having an off day.";

let heroSpeaking = false;

const setHeroState = (playing) => {
  heroSpeaking = playing;
  heroCard.classList.toggle('is-playing', playing);
  heroCardWave.classList.toggle('is-playing', playing);
  heroCardPlay.innerHTML = `<i class="ri-${playing ? 'stop' : 'play'}-fill"></i>`;
  heroCardPlay.setAttribute('aria-label', playing ? 'Stop the Aria sample' : 'Play the Aria voice sample');
  heroPlay.innerHTML = `<i class="ri-${playing ? 'stop' : 'play'}-fill"></i><span id="heroPlayLabel">${playing ? 'Stop' : 'Hear a sample'}</span>`;
  heroPlay.setAttribute('aria-label', playing ? 'Stop the Aria sample' : 'Play the Aria voice sample');
};

const toggleHero = () => {
  if (heroSpeaking) {
    stopSpeech();
    setHeroState(false);
    return;
  }

  speak({
    text: HERO_LINE,
    lang: 'en-US',
    pitch: 1.05,
    rate: 0.95,
    onStart: () => setHeroState(true),
    onEnd: () => setHeroState(false),
  });

  if (!speechSupported) {
    heroPlay.innerHTML = '<i class="ri-error-warning-line"></i><span id="heroPlayLabel">Speech unavailable</span>';
  }
};

heroCardPlay.addEventListener('click', toggleHero);
heroPlay.addEventListener('click', toggleHero);

/*=============== DEMO STUDIO ===============*/
const script = document.getElementById('script');
const charCount = document.getElementById('charCount');
const voiceSelect = document.getElementById('voiceSelect');
const rateInput = document.getElementById('rate');
const rateValue = document.getElementById('rateValue');
const styleChips = document.getElementById('styleChips');
const speakBtn = document.getElementById('speakBtn');
const speakLabel = document.getElementById('speakLabel');
const speakIcon = document.getElementById('speakIcon');
const speakStatus = document.getElementById('speakStatus');
const demoWave = document.getElementById('demoWave');
const nowVoice = document.getElementById('nowVoice');
const nowStyle = document.getElementById('nowStyle');
const nowAvatar = document.querySelector('.studio__avatar');

let currentPitch = 0.95;
let demoSpeaking = false;

const updateCount = () => {
  charCount.textContent = script.value.length;
};
script.addEventListener('input', updateCount);
updateCount();

function buildVoiceSelect() {
  if (!voiceSelect) return;
  const previous = voiceSelect.value;
  voiceSelect.innerHTML = '<option value="">Automatic · Aria</option>';

  if (!browserVoices.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = speechSupported ? 'System voice' : 'Speech unavailable';
    option.disabled = true;
    voiceSelect.appendChild(option);
    return;
  }

  const english = browserVoices.filter((voice) => voice.lang.toLowerCase().startsWith('en'));
  const others = browserVoices.filter((voice) => !voice.lang.toLowerCase().startsWith('en'));

  const addGroup = (label, voices) => {
    if (!voices.length) return;
    const group = document.createElement('optgroup');
    group.label = label;
    voices.forEach((voice) => {
      const option = document.createElement('option');
      option.value = voice.name;
      option.textContent = `${cleanVoiceName(voice.name)} · ${voice.lang.replace('_', '-')}`;
      group.appendChild(option);
    });
    voiceSelect.appendChild(group);
  };

  addGroup('English', english);
  addGroup('Other languages', others);

  if ([...voiceSelect.options].some((option) => option.value === previous)) {
    voiceSelect.value = previous;
  }
}

const setRateFill = () => {
  const min = Number(rateInput.min) || 0.7;
  const max = Number(rateInput.max) || 1.4;
  const percent = ((Number(rateInput.value) - min) / (max - min)) * 100;
  rateInput.style.setProperty('--fill', `${percent}%`);
  rateValue.textContent = `${Number(rateInput.value).toFixed(1)}×`;
};

rateInput.addEventListener('input', setRateFill);
setRateFill();

styleChips.addEventListener('click', (event) => {
  const chip = event.target.closest('.style-chip');
  if (!chip) return;

  styleChips.querySelectorAll('.style-chip').forEach((btn) => btn.classList.remove('is-active'));
  chip.classList.add('is-active');

  rateInput.value = chip.dataset.rate;
  currentPitch = Number(chip.dataset.pitch);
  setRateFill();
  nowStyle.textContent = `${chip.textContent} · ${chip.dataset.style === 'news' ? 'newsreader' : 'conversational'}`;
});

voiceSelect.addEventListener('change', () => {
  const option = voiceSelect.selectedOptions[0];
  const label = option && option.value ? option.textContent.split(' · ')[0] : 'Aria';
  nowVoice.textContent = label;
  nowAvatar.textContent = label.charAt(0).toUpperCase();
  speakStatus.textContent = 'Ready when you are';
  speakStatus.classList.remove('is-active');
});

const setDemoState = (playing, message) => {
  demoSpeaking = playing;
  speakBtn.classList.toggle('is-speaking', playing);
  speakIcon.className = playing ? 'ri-stop-fill' : 'ri-play-fill';
  speakLabel.textContent = playing ? 'Stop' : 'Generate speech';
  demoWave.classList.toggle('is-playing', playing);
  if (message) {
    speakStatus.textContent = message;
    speakStatus.classList.toggle('is-active', playing);
  }
};

speakBtn.addEventListener('click', () => {
  if (demoSpeaking) {
    stopSpeech();
    setDemoState(false, 'Stopped. The take is still yours.');
    return;
  }

  if (!script.value.trim()) {
    script.focus();
    return;
  }

  if (!speechSupported) {
    speakStatus.textContent = 'This browser can’t speak — try Chrome, Edge or Safari.';
    return;
  }

  const option = voiceSelect.selectedOptions[0];
  const voice = browserVoices.find((item) => item.name === voiceSelect.value) || null;
  const label = option && option.value ? option.textContent.split(' · ')[0] : 'Aria';

  speak({
    text: script.value.trim(),
    voice,
    pitch: currentPitch,
    rate: Number(rateInput.value),
    onStart: () => setDemoState(true, `Speaking · ${label}`),
    onEnd: (state) => {
      if (state === 'canceled') {
        setDemoState(false, 'Stopped.');
        return;
      }
      setDemoState(false, state === 'error'
        ? (browserVoices.length ? 'That voice hiccuped — try again.' : 'No voices installed in this browser — try Chrome, Edge or Safari.')
        : 'Finished. The Vocalis API sounds warmer.');
    },
  });
});

/*=============== VOICE CATALOG ===============*/
const voiceTiles = document.querySelectorAll('[data-voice-card]');
let playingTile = null;

voiceTiles.forEach((tile) => {
  const button = tile.querySelector('.voice-tile__play');
  const wave = tile.querySelector('.waveform');

  const resetTile = (active) => {
    tile.classList.toggle('is-playing', active);
    wave.classList.toggle('is-playing', active);
    button.innerHTML = `<i class="ri-${active ? 'stop' : 'play'}-fill"></i>`;
  };

  button.addEventListener('click', () => {
    if (playingTile === tile) {
      stopSpeech();
      resetTile(false);
      playingTile = null;
      return;
    }

    if (playingTile) {
      const prev = playingTile;
      prev.querySelector('.voice-tile__play').innerHTML = '<i class="ri-play-fill"></i>';
      prev.classList.remove('is-playing');
      prev.querySelector('.waveform').classList.remove('is-playing');
    }

    playingTile = tile;
    const name = tile.dataset.name;

    speak({
      text: tile.dataset.line,
      lang: tile.dataset.lang,
      pitch: Number(tile.dataset.pitch) || 1,
      rate: Number(tile.dataset.rate) || 1,
      onStart: () => resetTile(true),
      onEnd: () => {
        resetTile(false);
        if (playingTile === tile) playingTile = null;
      },
    });

    if (!speechSupported) {
      speakStatus.textContent = 'This browser can’t preview voices — try Chrome, Edge or Safari.';
      playingTile = null;
    } else {
      nowVoice.textContent = name;
      nowAvatar.textContent = name.charAt(0).toUpperCase();
    }
  });
});

if (speechSupported) {
  loadVoices();
  synth.addEventListener('voiceschanged', loadVoices);
  window.setTimeout(loadVoices, 400);
} else {
  speakStatus.textContent = 'Speech isn’t supported here — try Chrome, Edge or Safari.';
  if (speakBtn) {
    speakBtn.disabled = true;
    speakBtn.style.opacity = '0.55';
  }
}

/*=============== PRICING TOGGLE ===============*/
const billingButtons = document.querySelectorAll('.billing__btn');
const priceAmounts = document.querySelectorAll('.plan__amount');
const billingNotes = document.querySelectorAll('[data-billing-note]');

billingButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const period = button.dataset.billing;
    billingButtons.forEach((btn) => {
      const active = btn === button;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', String(active));
    });

    priceAmounts.forEach((amount) => {
      const value = amount.dataset[period];
      amount.textContent = `$${value}`;
    });

    billingNotes.forEach((note) => {
      const planName = note.closest('.plan').querySelector('.plan__name').textContent.trim();
      if (planName === 'Starter') {
        note.textContent = 'Free forever';
      } else {
        note.textContent = period === 'annual' ? 'Billed annually · save 20%' : 'Billed monthly';
      }
    });
  });
});

/*=============== FAQ ACCORDION ===============*/
const faqItems = document.querySelectorAll('.faq__item');

faqItems.forEach((item) => {
  const button = item.querySelector('.faq__q');
  button.addEventListener('click', () => {
    const isOpen = item.classList.contains('is-open');
    faqItems.forEach((other) => {
      other.classList.remove('is-open');
      other.querySelector('.faq__q').setAttribute('aria-expanded', 'false');
    });

    if (!isOpen) {
      item.classList.add('is-open');
      button.setAttribute('aria-expanded', 'true');
    }
  });
});
