/*=============== VOICE DESIGN CONSOLE ===============*/
(() => {
  'use strict';

  const { speak, stopSpeech, toast, speechSupported } = window.Vocalis;

  const designConsole = document.getElementById('designConsole');
  if (!designConsole) return;

  const warmth = document.getElementById('warmth');
  const pace = document.getElementById('pace');
  const brightness = document.getElementById('brightness');
  const warmthValue = document.getElementById('warmthValue');
  const paceValue = document.getElementById('paceValue');
  const brightnessValue = document.getElementById('brightnessValue');
  const descriptor = document.getElementById('consoleDescriptor');
  const playBtn = document.getElementById('consolePlay');
  const wave = document.getElementById('consoleWave');
  const saveBtn = document.getElementById('consoleSave');

  const PREVIEW_LINE =
    'Hi — I’m Aria. This is what warmth, pace and brightness sound like when they line up.';

  let playing = false;
  let saveTimer = null;
  let defaultSaveMarkup = saveBtn ? saveBtn.innerHTML : '';

  const setFill = (input) => {
    const min = Number(input.min) || 0;
    const max = Number(input.max) || 100;
    const percent = ((Number(input.value) - min) / (max - min)) * 100;
    input.style.setProperty('--fill', `${percent}%`);
  };

  const setPlaying = (active) => {
    playing = active;
    designConsole.classList.toggle('is-playing', active);
    wave.classList.toggle('is-playing', active);
    playBtn.classList.toggle('is-playing', active);
    playBtn.innerHTML = `<i class="ri-${active ? 'stop' : 'play'}-fill"></i>`;
    playBtn.setAttribute('aria-label', active ? 'Stop the voice preview' : 'Preview this voice');
  };

  const describe = () => {
    const warm = Number(warmth.value);
    const tempo = Number(pace.value);
    const word = warm >= 66 ? 'Warm' : warm >= 45 ? 'Balanced' : 'Cool';
    const speed = tempo < 0.88 ? 'unhurried' : tempo > 1.08 ? 'brisk' : 'conversational';
    return `${word} · ${speed} · EN-US`;
  };

  const updateReadout = () => {
    warmthValue.textContent = warmth.value;
    paceValue.textContent = `${Number(pace.value).toFixed(2)}×`;
    brightnessValue.textContent = brightness.value;
    descriptor.textContent = describe();
    [warmth, pace, brightness].forEach(setFill);
  };

  [warmth, pace, brightness].forEach((input) => {
    input.addEventListener('input', updateReadout);
  });

  updateReadout();

  const togglePreview = () => {
    if (playing) {
      stopSpeech();
      return;
    }

    const pitch = Math.min(1.4, Math.max(0.7, 0.8 + Number(warmth.value) * 0.0025 + Number(brightness.value) * 0.001));

    speak({
      text: PREVIEW_LINE,
      lang: 'en-US',
      pitch,
      rate: Number(pace.value),
      onStart: () => setPlaying(true),
      onEnd: () => setPlaying(false),
    });

    if (!speechSupported) {
      toast('This browser can’t synthesise speech — try Chrome, Edge or Safari.');
    }
  };

  if (playBtn) playBtn.addEventListener('click', togglePreview);

  if (saveBtn) {
    saveBtn.addEventListener('click', () => {
      const name = 'Aria · draft';
      toast(`${name} saved to your voice library.`);

      saveBtn.innerHTML = '<i class="ri-check-line"></i> Saved';
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(() => {
        saveBtn.innerHTML = defaultSaveMarkup;
      }, 2200);
    });
  }

  defaultSaveMarkup = saveBtn ? saveBtn.innerHTML : '';

  /*=============== DESIGN BRIEF FORM ===============*/
  const voiceForm = document.getElementById('voiceForm');
  if (!voiceForm) return;

  const nameInput = document.getElementById('voiceName');
  const ageSelect = document.getElementById('voiceAge');
  const languageSelect = document.getElementById('voiceLanguage');
  const descInput = document.getElementById('voiceDescription');
  const descCount = document.getElementById('voiceDescCount');
  const genderInputs = Array.from(voiceForm.querySelectorAll('input[name="voiceGender"]'));
  const briefAvatar = document.getElementById('briefAvatar');
  const briefName = document.getElementById('briefName');
  const briefMeta = document.getElementById('briefMeta');
  const briefDesc = document.getElementById('briefDesc');
  const briefStatus = document.getElementById('briefStatus');
  const voiceError = document.getElementById('voiceError');
  const createBtn = document.getElementById('createVoice');
  const createLabel = document.getElementById('createVoiceLabel');
  const createIcon = document.getElementById('createVoiceIcon');
  const resetBtn = document.getElementById('resetVoice');

  const DEFAULTS = {
    name: 'Aria',
    gender: 'Female',
    age: '25–34',
    language: 'English (US)',
  };
  const DESC_PLACEHOLDER = 'Add a short description to give the draft its character.';
  let draftTimer = null;

  const currentGender = () => (genderInputs.find((input) => input.checked) || genderInputs[0]).value;

  const setStatus = (saved) => {
    briefStatus.classList.toggle('is-saved', saved);
    briefStatus.innerHTML = `<span></span> ${saved ? 'Saved' : 'Draft'}`;
  };

  const updatePreview = () => {
    const name = nameInput.value.trim();
    const description = descInput.value.trim();
    const initials = name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word.charAt(0).toUpperCase())
      .join('') || 'V';

    briefAvatar.textContent = initials;
    briefName.textContent = name || 'Untitled voice';
    briefMeta.textContent = `${currentGender()} · ${ageSelect.value} · ${languageSelect.value}`;
    briefDesc.textContent = description || DESC_PLACEHOLDER;
    descCount.textContent = `${descInput.value.length} / 160`;
  };

  const clearDraftError = () => {
    voiceError.hidden = true;
    voiceError.textContent = '';
    nameInput.removeAttribute('aria-invalid');
    descInput.removeAttribute('aria-invalid');
  };

  const restoreCreateButton = () => {
    window.clearTimeout(draftTimer);
    createLabel.textContent = 'Create voice draft';
    createIcon.className = 'ri-add-line';
  };

  const markEdited = () => {
    clearDraftError();
    setStatus(false);
    restoreCreateButton();
    updatePreview();
  };

  [nameInput, ageSelect, languageSelect, descInput].forEach((field) => {
    field.addEventListener('input', markEdited);
    field.addEventListener('change', markEdited);
  });

  genderInputs.forEach((input) => {
    input.addEventListener('change', markEdited);
  });

  voiceForm.addEventListener('submit', (event) => {
    event.preventDefault();
    clearDraftError();

    const name = nameInput.value.trim();
    const description = descInput.value.trim();

    if (name.length < 2) {
      voiceError.textContent = 'Give your voice a name of at least two characters.';
      voiceError.hidden = false;
      nameInput.setAttribute('aria-invalid', 'true');
      nameInput.focus();
      return;
    }

    if (description.length < 12) {
      voiceError.textContent = 'Add a short description — at least 12 characters.';
      voiceError.hidden = false;
      descInput.setAttribute('aria-invalid', 'true');
      descInput.focus();
      return;
    }

    setStatus(true);
    toast(`${name} saved as a draft in your library.`);
    createLabel.textContent = 'Draft saved';
    createIcon.className = 'ri-check-line';
    window.clearTimeout(draftTimer);
    draftTimer = window.setTimeout(restoreCreateButton, 2400);
    updatePreview();
  });

  resetBtn.addEventListener('click', () => {
    nameInput.value = DEFAULTS.name;
    genderInputs.forEach((input) => {
      input.checked = input.value === DEFAULTS.gender;
    });
    ageSelect.value = DEFAULTS.age;
    languageSelect.value = DEFAULTS.language;
    descInput.value = '';
    setStatus(false);
    restoreCreateButton();
    clearDraftError();
    updatePreview();
    nameInput.focus();
  });

  updatePreview();
  setStatus(false);
})();
