/*=============== PLAYGROUND ===============*/
(() => {
  'use strict';

  const { speak, stopSpeech, toast, speechSupported } = window.Vocalis;

  const stage = document.getElementById('stage');
  if (!stage) return;

  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const VOICES = {
    aria: {
      name: 'Aria',
      desc: 'Warm · conversational',
      lang: 'en-US',
      pitch: 1.02,
      rate: 0.95,
      tone: 'linear-gradient(135deg,#f7bb3c,#d18600)',
      ink: '#14213d',
    },
    atlas: {
      name: 'Atlas',
      desc: 'Deep · documentary',
      lang: 'en-US',
      pitch: 0.8,
      rate: 0.9,
      tone: 'linear-gradient(135deg,#3a4d73,#101b2f)',
      ink: '',
    },
    june: {
      name: 'June',
      desc: 'Bright · friendly',
      lang: 'en-GB',
      pitch: 1.12,
      rate: 1.02,
      tone: 'linear-gradient(135deg,#f2e3c2,#cdb383)',
      ink: '#14213d',
    },
    nori: {
      name: 'Nori',
      desc: 'Calm · reassuring',
      lang: 'en-US',
      pitch: 0.95,
      rate: 0.92,
      tone: 'linear-gradient(135deg,#65738d,#2a3650)',
      ink: '',
    },
    kai: {
      name: 'Kai',
      desc: 'Energetic · promo',
      lang: 'en-AU',
      pitch: 1.12,
      rate: 1.12,
      tone: 'linear-gradient(135deg,#2b2b2b,#000000)',
      ink: '',
    },
    noor: {
      name: 'Noor',
      desc: 'Soft · storytelling',
      lang: 'en-IN',
      pitch: 1,
      rate: 0.88,
      tone: 'linear-gradient(135deg,#b47a2c,#7a4c00)',
      ink: '',
    },
    sable: {
      name: 'Sable',
      desc: 'Dry · deadpan',
      lang: 'en-US',
      pitch: 0.85,
      rate: 0.98,
      tone: 'linear-gradient(135deg,#c9a227,#6d5200)',
      ink: '#14213d',
    },
    wren: {
      name: 'Wren',
      desc: 'Crisp · explainer',
      lang: 'en-US',
      pitch: 1.1,
      rate: 1,
      tone: 'linear-gradient(135deg,#d8d2c4,#a79e8a)',
      ink: '#14213d',
    },
  };

  const SAMPLES = {
    product:
      'Meet Vocalis Studio — a voice you can direct like an actor, not a preset you hope fits. Write a line, shape the read, and ship it in seconds.',
    book:
      'The lighthouse had been dark for eleven years. Tonight, someone was climbing the stairs, and the lamp was already warm.',
    support:
      'I understand — let’s take that one step at a time. I’ve refunded the duplicate charge, and you’re not in trouble.',
  };

  const voiceSelect = document.getElementById('voiceSelect');
  const pgVoiceAvatar = document.getElementById('pgVoiceAvatar');
  const pgVoiceName = document.getElementById('pgVoiceName');
  const pgVoiceDesc = document.getElementById('pgVoiceDesc');
  const script = document.getElementById('script');
  const charCount = document.getElementById('charCount');
  const sampleChips = document.getElementById('sampleChips');
  const styleChips = document.getElementById('styleChips');
  const speed = document.getElementById('speed');
  const pitch = document.getElementById('pitch');
  const stability = document.getElementById('stability');
  const speedValue = document.getElementById('speedValue');
  const pitchValue = document.getElementById('pitchValue');
  const stabilityValue = document.getElementById('stabilityValue');
  const generateBtn = document.getElementById('generateBtn');
  const generateIcon = document.getElementById('generateIcon');
  const generateLabel = document.getElementById('generateLabel');
  const pgStatus = document.getElementById('pgStatus');
  const costLabel = document.getElementById('costLabel');
  const resetBtn = document.getElementById('resetBtn');
  const stageAvatar = document.getElementById('stageAvatar');
  const stageName = document.getElementById('stageName');
  const stageDesc = document.getElementById('stageDesc');
  const stageTime = document.getElementById('stageTime');
  const stageDuration = document.getElementById('stageDuration');
  const stageText = document.getElementById('stageText');
  const stageLang = document.getElementById('stageLang');
  const takesList = document.getElementById('takesList');
  const takesCount = document.getElementById('takesCount');
  const creditsValue = document.getElementById('creditsValue');

  const chips = $$('.style-chip', styleChips);

  let selected = 'aria';
  let speaking = false;
  let tickId = null;
  let credits = 8240;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const fmtTime = (seconds) => {
    const whole = Math.max(0, Math.floor(seconds));
    return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
  };

  const estimate = (text, rate) => {
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    return Math.max(2, Math.round(words / (2.4 * (Number(rate) || 1))));
  };

  const activeStyle = () => {
    const chip = chips.find((item) => item.classList.contains('is-active'));
    return chip ? chip.textContent.trim() : 'Custom';
  };

  const setFill = (input) => {
    const min = Number(input.min) || 0;
    const max = Number(input.max) || 100;
    const percent = ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty('--fill', `${percent}%`);
  };

  const updateSpeed = () => {
    speedValue.textContent = `${Number(speed.value).toFixed(2)}×`;
    setFill(speed);
  };

  const updatePitch = () => {
    const semitones = 12 * Math.log2(Number(pitch.value));
    pitchValue.textContent = `${semitones >= 0 ? '+' : ''}${semitones.toFixed(1)} st`;
    setFill(pitch);
  };

  const updateStability = () => {
    stabilityValue.textContent = `${stability.value}%`;
    setFill(stability);
  };

  const updateMeta = () => {
    const length = script.value.length;
    charCount.textContent = String(length);
    const cost = Math.ceil(length * 1.1);
    costLabel.textContent = `≈ ${cost.toLocaleString()} credits`;
    return cost;
  };

  const paintAvatar = (element, voice) => {
    element.textContent = voice.name.charAt(0).toUpperCase();
    element.style.setProperty('--tone', voice.tone);
    element.style.color = voice.ink;
  };

  const selectVoice = (slug, { applyDirection = false } = {}) => {
    const voice = VOICES[slug] ? slug : 'aria';
    selected = voice;
    const profile = VOICES[voice];

    voiceSelect.value = voice;
    pgVoiceName.textContent = profile.name;
    pgVoiceDesc.textContent = `${profile.desc} · ${profile.lang}`;
    paintAvatar(pgVoiceAvatar, profile);

    stageName.textContent = profile.name;
    stageDesc.textContent = profile.desc;
    stageLang.textContent = profile.lang;
    paintAvatar(stageAvatar, profile);

    if (applyDirection && !speaking) {
      chips.forEach((chip) => chip.classList.remove('is-active'));
      speed.value = String(clamp(profile.rate, 0.7, 1.3));
      pitch.value = String(clamp(profile.pitch, 0.8, 1.2));
      updateSpeed();
      updatePitch();
      pgStatus.textContent = `Loaded ${profile.name} — direct the read, then generate.`;
    }
  };

  if (voiceSelect) {
    voiceSelect.addEventListener('change', () => selectVoice(voiceSelect.value, { applyDirection: true }));
  }

  [speed, pitch].forEach((input) => {
    input.addEventListener('input', () => {
      chips.forEach((chip) => chip.classList.remove('is-active'));
    });
  });

  speed.addEventListener('input', updateSpeed);
  pitch.addEventListener('input', updatePitch);
  stability.addEventListener('input', updateStability);

  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      chips.forEach((item) => item.classList.toggle('is-active', item === chip));
      speed.value = chip.dataset.rate;
      pitch.value = String(clamp(Number(chip.dataset.pitch) || 1, 0.8, 1.2));
      updateSpeed();
      updatePitch();
      pgStatus.textContent = `${chip.textContent.trim()} direction applied.`;
    });
  });

  script.addEventListener('input', () => {
    updateMeta();
    if (!speaking) pgStatus.textContent = 'Ready when you are.';
  });

  if (sampleChips) {
    sampleChips.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-sample]');
      if (!chip) return;
      script.value = SAMPLES[chip.dataset.sample] || '';
      updateMeta();
      pgStatus.textContent = 'Sample loaded — generate when ready.';
      script.focus();
    });
  }

  const startTicker = (duration) => {
    if (tickId) window.clearInterval(tickId);
    stageTime.textContent = '0:00';
    stageDuration.textContent = fmtTime(duration);
    const startedAt = performance.now();

    tickId = window.setInterval(() => {
      const elapsed = (performance.now() - startedAt) / 1000;
      stageTime.textContent = fmtTime(Math.min(elapsed, duration));
    }, 250);
  };

  const stopTicker = (reset) => {
    if (tickId) {
      window.clearInterval(tickId);
      tickId = null;
    }
    if (reset) stageTime.textContent = '0:00';
  };

  const setSpeakingState = (active) => {
    speaking = active;
    stage.classList.toggle('is-speaking', active);
    generateIcon.className = `ri-${active ? 'stop' : 'play'}-fill`;
    generateLabel.textContent = active ? 'Stop' : 'Generate speech';
  };

  const updateTakesCount = () => {
    if (!takesCount) return;
    const total = $$('.take', takesList).length;
    takesCount.textContent = `${total} take${total === 1 ? '' : 's'}`;
  };

  const addTake = ({ text, voice, rate, pitchValue: usedPitch, duration, style }) => {
    const item = document.createElement('li');
    item.className = 'take';
    item.dataset.text = text;
    item.dataset.lang = voice.lang;
    item.dataset.pitch = String(usedPitch);
    item.dataset.rate = String(rate);
    item.dataset.voice = voice.name;

    const play = document.createElement('button');
    play.className = 'take__play';
    play.type = 'button';
    play.setAttribute('aria-label', `Replay the ${voice.name} take`);
    play.innerHTML = '<i class="ri-play-fill"></i>';

    const copy = document.createElement('div');
    copy.className = 'take__copy';
    const headline = document.createElement('strong');
    headline.textContent = text.length > 46 ? `${text.slice(0, 46).trimEnd()}…` : text;
    const meta = document.createElement('span');
    meta.textContent = `${voice.name} · ${style} · ${fmtTime(duration)}`;
    copy.append(headline, meta);

    const more = document.createElement('button');
    more.className = 'icon-btn';
    more.type = 'button';
    more.setAttribute('aria-label', 'Take options');
    more.dataset.toast = 'Render options are not wired in this demo.';
    more.innerHTML = '<i class="ri-more-2-line"></i>';

    item.append(play, copy, more);
    takesList.prepend(item);
    updateTakesCount();
  };

  const playTake = (take) => {
    const voice = Object.values(VOICES).find((item) => item.name === take.dataset.voice) || VOICES[selected];
    const text = take.dataset.text;
    const rate = Number(take.dataset.rate) || 1;
    const usedPitch = Number(take.dataset.pitch) || 1;
    const duration = estimate(text, rate);
    const playBtn = take.querySelector('.take__play');

    stageName.textContent = voice.name;
    stageDesc.textContent = voice.desc;
    stageLang.textContent = take.dataset.lang;
    paintAvatar(stageAvatar, voice);
    stageText.textContent = `“${text}”`;
    stageDuration.textContent = fmtTime(duration);

    const started = speak({
      text,
      lang: take.dataset.lang,
      pitch: usedPitch,
      rate,
      onStart: () => {
        take.classList.add('is-playing');
        playBtn.innerHTML = '<i class="ri-stop-fill"></i>';
        stage.classList.add('is-speaking');
        startTicker(duration);
        pgStatus.textContent = `Playing ${voice.name} take…`;
      },
      onEnd: (state) => {
        take.classList.remove('is-playing');
        playBtn.innerHTML = '<i class="ri-play-fill"></i>';
        stage.classList.remove('is-speaking');
        stopTicker(state !== 'end');

        if (state === 'end') {
          stageTime.textContent = fmtTime(duration);
          pgStatus.textContent = 'Replay finished. Ready when you are.';
        } else if (state === 'canceled') {
          pgStatus.textContent = 'Stopped.';
        } else if (state === 'unsupported') {
          pgStatus.textContent = 'This browser can’t synthesise speech — try Chrome, Edge or Safari.';
        } else {
          pgStatus.textContent = 'That replay hiccuped — try again.';
        }
      },
    });

    if (!started) toast('This browser can’t preview takes — try Chrome, Edge or Safari.');
  };

  takesList.addEventListener('click', (event) => {
    const button = event.target.closest('.take__play');
    if (!button) return;
    const take = button.closest('.take');
    if (!take) return;

    if (take.classList.contains('is-playing')) {
      stopSpeech();
      return;
    }

    playTake(take);
  });

  generateBtn.addEventListener('click', () => {
    if (speaking) {
      stopSpeech();
      return;
    }

    const text = script.value.trim();
    if (!text) {
      script.focus();
      pgStatus.textContent = 'Write a line first — even a short one.';
      return;
    }

    const voice = VOICES[selected];
    const rate = Number(speed.value);
    const usedPitch = Number(pitch.value);
    const duration = estimate(text, rate);
    const cost = updateMeta();
    const style = activeStyle();

    stageText.textContent = `“${text}”`;
    stageName.textContent = voice.name;
    stageDesc.textContent = voice.desc;
    stageLang.textContent = voice.lang;
    paintAvatar(stageAvatar, voice);

    const started = speak({
      text,
      lang: voice.lang,
      pitch: usedPitch,
      rate,
      onStart: () => {
        setSpeakingState(true);
        pgStatus.textContent = `Speaking · ${voice.name}`;
        startTicker(duration);
      },
      onEnd: (state) => {
        setSpeakingState(false);
        stopTicker(state !== 'end');

        if (state === 'end') {
          stageTime.textContent = fmtTime(duration);
          credits = Math.max(0, credits - cost);
          if (creditsValue) creditsValue.textContent = credits.toLocaleString();
          addTake({ text, voice, rate, pitchValue: usedPitch, duration, style });
          pgStatus.textContent = `Take saved · ${fmtTime(duration)} · −${cost.toLocaleString()} credits`;
        } else if (state === 'canceled') {
          pgStatus.textContent = 'Stopped. Nothing was charged.';
        } else if (state === 'unsupported') {
          pgStatus.textContent = 'This browser can’t synthesise speech — try Chrome, Edge or Safari.';
        } else {
          pgStatus.textContent = 'That render hiccuped — try again.';
        }
      },
    });

    if (!started) toast('This browser can’t synthesise speech — try Chrome, Edge or Safari.');
  });

  resetBtn.addEventListener('click', () => {
    const warm = chips[0];
    chips.forEach((chip) => chip.classList.toggle('is-active', chip === warm));
    speed.value = warm.dataset.rate;
    pitch.value = String(clamp(Number(warm.dataset.pitch) || 1, 0.8, 1.2));
    stability.value = '78';
    updateSpeed();
    updatePitch();
    updateStability();
    pgStatus.textContent = 'Direction reset to Warm.';
  });

  const requested = new URLSearchParams(window.location.search).get('voice');
  selectVoice(requested && VOICES[requested] ? requested : 'aria', { applyDirection: true });
  pgStatus.textContent = 'Ready when you are.';

  updateSpeed();
  updatePitch();
  updateStability();
  updateMeta();
  updateTakesCount();

  if (!speechSupported) {
    pgStatus.textContent = 'Browser speech unavailable — try Chrome, Edge or Safari.';
  }
})();
