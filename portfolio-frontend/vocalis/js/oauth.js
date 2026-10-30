/*=============== OAUTH: SIGN IN + CONSENT ===============*/
(() => {
  'use strict';

  const { toast } = window.Vocalis;

  const authCard = document.getElementById('authCard');
  const consentCard = document.getElementById('consentCard');
  const deniedCard = document.getElementById('deniedCard');
  if (!authCard || !consentCard || !deniedCard) return;

  const authIcon = document.getElementById('authIcon');
  const authKicker = document.getElementById('authKicker');
  const authHeading = document.getElementById('authHeading');
  const authSub = document.getElementById('authSub');
  const tabSignin = document.getElementById('tabSignin');
  const tabRegister = document.getElementById('tabRegister');
  const googleBtn = document.getElementById('googleBtn');
  const googleLabel = document.getElementById('googleLabel');
  const authForm = document.getElementById('authForm');
  const authName = document.getElementById('authName');
  const authEmail = document.getElementById('authEmail');
  const authPassword = document.getElementById('authPassword');
  const passwordToggle = document.getElementById('passwordToggle');
  const authTerms = document.getElementById('authTerms');
  const authError = document.getElementById('authError');
  const authSubmit = document.getElementById('authSubmit');
  const authSubmitLabel = document.getElementById('authSubmitLabel');
  const authSubmitIcon = document.getElementById('authSubmitIcon');
  const consentPreview = document.getElementById('consentPreview');
  const allowBtn = document.getElementById('allowBtn');
  const allowLabel = document.getElementById('allowLabel');
  const allowIcon = document.getElementById('allowIcon');
  const denyBtn = document.getElementById('denyBtn');
  const retryBtn = document.getElementById('retryBtn');
  const switchBtn = document.getElementById('switchBtn');
  const accountName = document.getElementById('accountName');
  const accountEmail = document.getElementById('accountEmail');
  const accountAvatar = document.getElementById('accountAvatar');
  const clientIcon = document.getElementById('clientIcon');

  const CLIENTS = {
    narrate: {
      name: 'Narrate Studio',
      mark: 'N',
      tone: 'linear-gradient(135deg,#14213d,#33486f)',
    },
    lumen: {
      name: 'Lumen Audio',
      mark: 'L',
      tone: 'linear-gradient(135deg,#f7bb3c,#d18600)',
    },
    hearth: {
      name: 'Hearth',
      mark: 'H',
      tone: 'linear-gradient(135deg,#000000,#2b2b2b)',
    },
  };

  const params = new URLSearchParams(window.location.search);
  const requested = params.get('client');
  const client = (requested && CLIENTS[requested.toLowerCase()]) || null;
  const registerOnLoad = params.get('intent') === 'signup';

  document.title = client
    ? `Authorize ${client.name} — Vocalis`
    : registerOnLoad
      ? 'Create account — Vocalis'
      : 'Sign in — Vocalis';

  if (client) {
    document.querySelectorAll('[data-client]').forEach((el) => {
      el.textContent = client.name;
    });

    if (clientIcon) {
      clientIcon.textContent = client.mark;
      clientIcon.style.background = client.tone;
      clientIcon.style.color = '#ffffff';
    }
  }

  if (authIcon && client) {
    authIcon.textContent = client.mark;
    authIcon.style.background = client.tone;
    authIcon.style.color = '#ffffff';
  }

  if (consentPreview) consentPreview.hidden = Boolean(client);

  const registerOnly = Array.from(document.querySelectorAll('[data-register-only]'));
  const signinOnly = Array.from(document.querySelectorAll('[data-signin-only]'));

  let mode = registerOnLoad ? 'register' : 'signin';
  let busy = false;

  const clearError = () => {
    authError.hidden = true;
    authError.textContent = '';
    [authName, authEmail, authPassword, authTerms].forEach((field) => {
      field.removeAttribute('aria-invalid');
    });
  };

  const fail = (message, field) => {
    authError.textContent = message;
    authError.hidden = false;
    field.setAttribute('aria-invalid', 'true');
    field.focus();
  };

  const applyCopy = () => {
    const register = mode === 'register';

    if (client) {
      authKicker.textContent = 'Authorize application';
      authHeading.textContent = register ? 'Create your account' : 'Sign in to continue';
      authSub.textContent = register
        ? `New to Vocalis? Create an account to authorize ${client.name}.`
        : `Use your Vocalis account to authorize ${client.name}.`;
    } else {
      authKicker.textContent = 'Vocalis account';
      authHeading.textContent = register ? 'Create your account' : 'Welcome back';
      authSub.textContent = register
        ? 'Start designing voices free — 10,000 characters, no card needed.'
        : 'Sign in to open your voice studio.';
    }

    authSubmitLabel.textContent = register ? 'Create account' : 'Sign in';
    authPassword.autocomplete = register ? 'new-password' : 'current-password';
    authName.required = register;
  };

  const setMode = (next) => {
    mode = next;
    const register = mode === 'register';

    registerOnly.forEach((el) => {
      el.hidden = !register;
    });
    signinOnly.forEach((el) => {
      el.hidden = register;
    });

    tabSignin.classList.toggle('is-active', !register);
    tabRegister.classList.toggle('is-active', register);
    tabSignin.setAttribute('aria-pressed', String(!register));
    tabRegister.setAttribute('aria-pressed', String(register));

    clearError();
    applyCopy();
  };

  const stopBusy = () => {
    busy = false;
    authSubmit.disabled = false;
    googleBtn.disabled = false;
    authSubmit.classList.remove('is-loading');
    googleBtn.classList.remove('is-loading');
    authSubmitIcon.className = 'ri-arrow-right-line';
    googleLabel.textContent = 'Continue with Google';
    authSubmitLabel.textContent = mode === 'register' ? 'Create account' : 'Sign in';
  };

  const initialsFrom = (name) => {
    const words = name.split(/\s+/).filter(Boolean);
    return words.slice(0, 2).map((word) => word.charAt(0).toUpperCase()).join('') || 'VU';
  };

  const nameFromEmail = (email) => {
    const local = email.split('@')[0].replace(/[._-]+/g, ' ').trim();
    const words = local.split(/\s+/).filter(Boolean);
    const name = words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    return name || 'Vocalis user';
  };

  const setAccount = (name, email) => {
    accountName.textContent = name;
    accountEmail.textContent = email;
    accountAvatar.textContent = initialsFrom(name);
  };

  const showConsent = () => {
    authCard.hidden = true;
    deniedCard.hidden = true;
    consentCard.hidden = false;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    allowBtn.focus({ preventScroll: true });
  };

  const finishAuth = () => {
    if (client) {
      showConsent();
    } else {
      window.location.href = 'dashboard.html';
    }
  };

  tabSignin.addEventListener('click', () => {
    if (busy) return;
    setMode('signin');
    authEmail.focus();
  });

  tabRegister.addEventListener('click', () => {
    if (busy) return;
    setMode('register');
    authName.focus();
  });

  [authName, authEmail, authPassword].forEach((field) => {
    field.addEventListener('input', clearError);
  });
  authTerms.addEventListener('change', clearError);

  passwordToggle.addEventListener('click', () => {
    const show = authPassword.type === 'password';
    authPassword.type = show ? 'text' : 'password';
    passwordToggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    passwordToggle.setAttribute('aria-pressed', String(show));
    passwordToggle.innerHTML = `<i class="ri-eye-${show ? 'off-' : ''}line"></i>`;
    authPassword.focus();
  });

  authForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (busy) return;

    clearError();

    const name = authName.value.trim();
    const email = authEmail.value.trim();
    const password = authPassword.value;

    if (mode === 'register' && name.length < 2) {
      fail('Enter your full name.', authName);
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      fail('Enter a valid email address.', authEmail);
      return;
    }
    if (password.length < 8) {
      fail('Use at least 8 characters for your password.', authPassword);
      return;
    }
    if (mode === 'register' && !authTerms.checked) {
      fail('Please accept the terms to create an account.', authTerms);
      return;
    }

    busy = true;
    authSubmit.disabled = true;
    googleBtn.disabled = true;
    authSubmit.classList.add('is-loading');
    authSubmitLabel.textContent = mode === 'register' ? 'Creating account…' : 'Signing in…';
    authSubmitIcon.className = 'ri-loader-4-line';

    window.setTimeout(() => {
      setAccount(mode === 'register' ? name : nameFromEmail(email), email);
      stopBusy();
      if (client) toast(`Signed in as ${email}`);
      finishAuth();
    }, 750);
  });

  googleBtn.addEventListener('click', () => {
    if (busy) return;

    clearError();
    busy = true;
    googleBtn.disabled = true;
    authSubmit.disabled = true;
    googleBtn.classList.add('is-loading');
    googleLabel.textContent = 'Connecting to Google…';

    window.setTimeout(() => {
      setAccount('Maya Chen', 'maya.chen@gmail.com');
      stopBusy();
      if (client) toast('Signed in with Google.');
      finishAuth();
    }, 900);
  });

  allowBtn.addEventListener('click', () => {
    if (!client || allowBtn.classList.contains('is-loading')) return;

    allowBtn.classList.add('is-loading');
    allowBtn.disabled = true;
    denyBtn.disabled = true;
    allowLabel.textContent = 'Authorizing…';
    allowIcon.className = 'ri-loader-4-line';

    window.setTimeout(() => {
      window.location.href = `dashboard.html?authorized=1&client=${encodeURIComponent(client.name)}`;
      allowBtn.classList.remove('is-loading');
      allowBtn.disabled = false;
      denyBtn.disabled = false;
      allowLabel.textContent = 'Allow access';
      allowIcon.className = 'ri-arrow-right-line';
    }, 1100);
  });

  denyBtn.addEventListener('click', () => {
    consentCard.hidden = true;
    deniedCard.hidden = false;
    retryBtn.focus();
  });

  retryBtn.addEventListener('click', () => {
    deniedCard.hidden = true;
    consentCard.hidden = false;
    allowBtn.focus();
  });

  switchBtn.addEventListener('click', () => {
    consentCard.hidden = true;
    deniedCard.hidden = true;
    authCard.hidden = false;
    setMode('signin');
    authEmail.value = accountEmail.textContent.trim();
    authPassword.value = '';
    authEmail.focus();
  });

  setMode(mode);
})();
