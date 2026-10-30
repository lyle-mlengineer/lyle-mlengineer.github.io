/*=============== HELPERS ===============*/
const $ = (selector, context = document) => context.querySelector(selector)
const $$ = (selector, context = document) => [...context.querySelectorAll(selector)]

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const store = {
   get(key, fallback = null) {
      try {
         const raw = localStorage.getItem(key)
         return raw === null ? fallback : JSON.parse(raw)
      } catch {
         return fallback
      }
   },
   set(key, value) {
      try {
         localStorage.setItem(key, JSON.stringify(value))
         return true
      } catch {
         return false
      }
   },
   remove(key) {
      try {
         localStorage.removeItem(key)
      } catch {}
   }
}

const USER_KEY = 'voxa-user'
const DRAFT_KEY = 'voxa-draft'
const EPISODES_KEY = 'voxa-episodes-v1'

const DEFAULT_USER = {
   name: 'Maya Chen',
   email: 'maya@studio.fm',
   plan: 'Creator'
}

const getUser = () => ({ ...DEFAULT_USER, ...(store.get(USER_KEY) || {}) })
const initialsOf = name => name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase()
const firstNameOf = name => name.trim().split(/\s+/)[0]
const titleCase = value => value.replace(/[._-]+/g, ' ').replace(/\b\w/g, char => char.toUpperCase())

const getUserEpisodes = () => {
   const list = store.get(EPISODES_KEY, [])
   return Array.isArray(list) ? list : []
}

const addUserEpisode = episode => {
   const next = [episode, ...getUserEpisodes()].slice(0, 12)
   store.set(EPISODES_KEY, next)
}

const debounce = (fn, delay = 450) => {
   let timer
   return (...args) => {
      clearTimeout(timer)
      timer = setTimeout(() => fn(...args), delay)
   }
}

const formatDate = date => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

const formatClock = seconds => {
   const total = Math.max(1, Math.round(seconds))
   const minutes = Math.floor(total / 60)
   const rest = total % 60
   return `${minutes}:${String(rest).padStart(2, '0')}`
}

/*=============== ACCOUNTS ===============*/
const ACCOUNTS_KEY = 'voxa-accounts-v1'
const REMEMBER_KEY = 'voxa-remember'
const MIN_PASSWORD = 8

// Demo-only digest so raw passwords never sit in localStorage. This is not credential security.
const demoHash = value => {
   let hash = 0x811c9dc5
   for (const char of value) {
      hash ^= char.charCodeAt(0)
      hash = Math.imul(hash, 0x01000193)
   }
   return (hash >>> 0).toString(36)
}

const getAccounts = () => {
   const list = store.get(ACCOUNTS_KEY, [])
   return Array.isArray(list) ? list.filter(account => account && account.email && account.name) : []
}

const findAccount = email => {
   const value = email.trim().toLowerCase()
   return getAccounts().find(account => account.email.toLowerCase() === value) || null
}

const saveAccount = account => {
   const next = [account, ...getAccounts().filter(item => item.email.toLowerCase() !== account.email.toLowerCase())]
   return store.set(ACCOUNTS_KEY, next.slice(0, 24))
}

const createAccount = ({ name, email, password, plan }) => saveAccount({
   name,
   email,
   plan,
   pass: demoHash(password),
   createdAt: new Date().toISOString()
})

const isEmail = value => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.trim())

const clearFieldError = input => {
   input.closest('.field')?.classList.remove('is-error')
   input.removeAttribute('aria-invalid')
}

const markFieldError = (input, message) => {
   const field = input.closest('.field')
   if (!field) return
   field.classList.add('is-error')
   input.setAttribute('aria-invalid', 'true')
   const error = field.querySelector('.field__error')
   if (error && message) error.textContent = message
}

const showFormAlert = (el, message, link) => {
   if (!el) return
   el.textContent = ''
   if (!message) {
      el.hidden = true
      return
   }
   el.append(message)
   if (link) {
      const anchor = document.createElement('a')
      anchor.href = link.href
      anchor.textContent = link.text
      el.append(' ', anchor)
   }
   el.hidden = false
}

const passwordScore = value => {
   const rules = {
      length: value.length >= MIN_PASSWORD,
      letter: /[a-z]/i.test(value),
      number: /\d/.test(value)
   }
   const score = Object.values(rules).filter(Boolean).length
   const labels = ['Use 8 or more characters', 'Still too easy', 'Getting closer', 'Strong enough']
   return { rules, score, label: labels[value ? score : 0] }
}

const signInAs = (profile, message) => {
   store.set(USER_KEY, { ...getUser(), ...profile })
   showToast(message)
   setTimeout(() => { window.location.href = 'dashboard.html' }, 650)
}

document.addEventListener('click', event => {
   const toggle = event.target.closest('[data-pw-toggle]')
   if (!toggle) return
   const input = toggle.closest('.input-wrap')?.querySelector('input')
   if (!input) return
   const show = input.type === 'password'
   input.type = show ? 'text' : 'password'
   toggle.innerHTML = show
      ? '<i class="ri-eye-off-line" aria-hidden="true"></i>'
      : '<i class="ri-eye-line" aria-hidden="true"></i>'
   toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password')
})

document.addEventListener('click', event => {
   const button = event.target.closest('[data-social-auth]')
   if (!button) return
   button.disabled = true
   signInAs({ name: getUser().name, email: getUser().email }, `Signed in with ${button.dataset.socialAuth}.`)
})

/*=============== CLONED VOICES ===============*/
const VOICES_KEY = 'voxa-voices-v1'
const SAMPLE_MIN_SECONDS = 10
const REC_MAX_SECONDS = 90
const UPLOAD_MAX_SECONDS = 180
const UPLOAD_MAX_BYTES = 25 * 1024 * 1024
const PERSIST_MAX_BYTES = 1.2 * 1024 * 1024
const CLONE_PALETTES = ['c-mint', 'c-clay', 'c-blue', 'c-sun', 'c-lilac', 'c-moss', 'c-rose']
const CLONE_VARIANTS = ['wave', 'rings', 'disc', 'grid', 'type']

const getClonedVoices = () => {
   const list = store.get(VOICES_KEY, [])
   return Array.isArray(list) ? list.filter(voice => voice && voice.id && voice.name) : []
}

const findClonedVoice = id => getClonedVoices().find(voice => voice.id === id) || null

const VOICE_SLOTS = { Starter: 1, Creator: 3, Studio: null }

const voiceSlotLimit = () => (getUser().plan in VOICE_SLOTS ? VOICE_SLOTS[getUser().plan] : VOICE_SLOTS.Creator)

const voiceSlotUsage = () => ({ used: getClonedVoices().length, limit: voiceSlotLimit() })

const voiceUsage = name => getUserEpisodes().filter(episode => (episode.voices || []).includes(name)).length

const sampleCache = new Map()
const clonedSample = voice => (voice ? sampleCache.get(voice.id) || voice.audio || null : null)

const releaseUrl = url => {
   if (!url || [...sampleCache.values()].includes(url)) return
   URL.revokeObjectURL(url)
}

const persistClonedVoice = voice => {
   const strip = list => list.map(({ sessionUrl, ...rest }) => rest)
   const next = strip([voice, ...getClonedVoices().filter(item => item.id !== voice.id)])
   if (store.set(VOICES_KEY, next)) return 'saved'

   const slim = next.map(({ audio, ...rest }) => ({ ...rest, audio: null }))
   return store.set(VOICES_KEY, slim) ? 'slim' : 'failed'
}

const updateClonedVoice = (id, patch) => {
   const next = getClonedVoices().map(voice => (voice.id === id ? { ...voice, ...patch } : voice))
   return store.set(VOICES_KEY, next)
}

const dropClonedVoice = id => {
   const next = getClonedVoices().filter(voice => voice.id !== id)
   if (!store.set(VOICES_KEY, next)) return false
   const cached = sampleCache.get(id)
   if (cached) URL.revokeObjectURL(cached)
   sampleCache.delete(id)
   return true
}

let sampleAudio = null
let sampleButton = null

const stopSample = () => {
   if (sampleAudio) {
      sampleAudio.pause()
      sampleAudio.src = ''
      sampleAudio = null
   }
   if (sampleButton) {
      sampleButton.classList.remove('is-playing')
      const icon = sampleButton.querySelector('i')
      if (icon) icon.className = 'ri-play-fill'
   }
   sampleAudio = null
   sampleButton = null
}

document.addEventListener('click', event => {
   const button = event.target.closest('[data-voice-play]')
   if (!button) return

   const voice = findClonedVoice(button.dataset.voicePlay)
   const src = clonedSample(voice)
   if (!voice || !src) {
      showToast('This voice was built from a sample we could not keep.', 'error')
      return
   }

   const replay = sampleButton === button
   stopSample()
   if (replay) return

   if ('speechSynthesis' in window) window.speechSynthesis.cancel()
   if (activeSpeechButton) stopSpeech()

   sampleAudio = new Audio(src)
   sampleAudio.onended = stopSample
   sampleAudio.onerror = stopSample
   sampleButton = button
   button.classList.add('is-playing')
   const icon = button.querySelector('i')
   if (icon) icon.className = 'ri-stop-fill'
   sampleAudio.play().catch(stopSample)
})

const blobToDataUrl = blob => new Promise(resolve => {
   const reader = new FileReader()
   reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null)
   reader.onerror = () => resolve(null)
   reader.readAsDataURL(blob)
})

const readAudioDuration = url => new Promise(resolve => {
   const probe = new Audio()
   let settled = false

   const finish = seconds => {
      if (settled) return
      settled = true
      clearTimeout(guard)
      probe.onloadedmetadata = null
      probe.ondurationchange = null
      probe.onerror = null
      probe.src = ''
      resolve(seconds)
   }

   probe.preload = 'metadata'
   probe.onloadedmetadata = () => {
      if (Number.isFinite(probe.duration) && probe.duration > 0) return finish(probe.duration)
      probe.currentTime = 1e6
      probe.ondurationchange = () => {
         if (Number.isFinite(probe.duration) && probe.duration > 0) finish(probe.duration)
      }
   }
   probe.onerror = () => finish(null)
   const guard = setTimeout(() => finish(null), 3500)
   probe.src = url
})

const coverForVoice = voice => ({
   variant: voice.variant || 'wave',
   palette: voice.palette || 'c-mint',
   letter: (voice.name || 'V').replace(/[^a-z0-9]/gi, '').charAt(0) || 'V'
})

const sourceLabel = voice => (voice.source === 'upload' ? 'Uploaded' : 'Recorded')

const isVoiceNameFree = name => {
   const value = name.trim().toLowerCase()
   return !getClonedVoices().some(voice => voice.name.trim().toLowerCase() === value)
}

const voiceNameValid = name => name.trim().length >= 2 && isVoiceNameFree(name)

$$('[data-scroll-target]').forEach(node => {
   node.addEventListener('click', event => {
      const target = document.querySelector(node.dataset.scrollTarget)
      if (!target) return
      event.preventDefault()
      target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
   })
})

/*=============== TOAST ===============*/
let toastRegion = null

const showToast = (message, tone = 'ok') => {
   if (!toastRegion) {
      toastRegion = document.createElement('div')
      toastRegion.className = 'toast-region'
      toastRegion.setAttribute('role', 'status')
      toastRegion.setAttribute('aria-live', 'polite')
      document.body.appendChild(toastRegion)
   }

   const toast = document.createElement('div')
   toast.className = `toast${tone === 'error' ? ' toast--error' : ''}`

   const icon = document.createElement('i')
   icon.className = tone === 'error' ? 'ri-error-warning-line' : 'ri-checkbox-circle-fill'
   icon.setAttribute('aria-hidden', 'true')

   const text = document.createElement('span')
   text.textContent = message

   toast.append(icon, text)
   toastRegion.appendChild(toast)
   requestAnimationFrame(() => toast.classList.add('is-in'))

   setTimeout(() => {
      toast.classList.remove('is-in')
      setTimeout(() => toast.remove(), 350)
   }, 3200)
}

/*=============== USER CHROME ===============*/
const fillUserChrome = () => {
   const user = getUser()
   $$('[data-user-name]').forEach(el => { el.textContent = user.name })
   $$('[data-user-first]').forEach(el => { el.textContent = firstNameOf(user.name) })
   $$('[data-user-email]').forEach(el => { el.textContent = user.email })
   $$('[data-user-initials]').forEach(el => { el.textContent = initialsOf(user.name) })
   $$('[data-user-plan]').forEach(el => { el.textContent = `${user.plan} plan` })
}

fillUserChrome()

document.addEventListener('click', event => {
   const signout = event.target.closest('[data-signout]')
   if (signout) {
      store.remove(USER_KEY)
      showToast('Signed out of this demo studio.')
   }
})

/*=============== ACCOUNT MENU ===============*/
const userMenu = $('.user-menu')
const accountToggle = $('#account-toggle')

if (userMenu && accountToggle) {
   const closeMenu = () => {
      userMenu.classList.remove('is-open')
      accountToggle.setAttribute('aria-expanded', 'false')
   }

   accountToggle.addEventListener('click', event => {
      event.stopPropagation()
      const open = !userMenu.classList.contains('is-open')
      userMenu.classList.toggle('is-open', open)
      accountToggle.setAttribute('aria-expanded', String(open))
   })

   document.addEventListener('click', event => {
      if (!userMenu.contains(event.target)) closeMenu()
   })

   document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeMenu()
   })
}

/*=============== MOBILE APP NAV ===============*/
const mobileToggle = $('#app-menu-toggle')
const mobileNav = $('#app-mobile-nav')

if (mobileToggle && mobileNav) {
   const closeMobile = () => {
      mobileNav.hidden = true
      mobileToggle.setAttribute('aria-expanded', 'false')
      mobileToggle.innerHTML = '<i class="ri-menu-3-line"></i>'
   }

   mobileToggle.addEventListener('click', () => {
      const open = mobileNav.hidden
      mobileNav.hidden = !open
      mobileToggle.setAttribute('aria-expanded', String(open))
      mobileToggle.innerHTML = open
         ? '<i class="ri-close-large-line"></i>'
         : '<i class="ri-menu-3-line"></i>'
   })

   $$('a', mobileNav).forEach(link => link.addEventListener('click', closeMobile))

   window.addEventListener('resize', () => {
      if (window.innerWidth >= 900) closeMobile()
   })
}

/*=============== MODALS ===============*/
const openModal = id => {
   const modal = document.getElementById(id)
   if (!modal) return null

   modal.classList.add('is-open')
   modal.setAttribute('aria-hidden', 'false')
   document.body.classList.add('is-locked')

   const focusTarget = modal.querySelector('[data-autofocus]') || modal.querySelector('button, a, input, select, textarea')
   if (focusTarget) setTimeout(() => focusTarget.focus(), 80)
   return modal
}

const closeModal = modal => {
   if (!modal) return
   modal.classList.remove('is-open')
   modal.setAttribute('aria-hidden', 'true')
   if (!$('.modal.is-open')) document.body.classList.remove('is-locked')
}

document.addEventListener('click', event => {
   const opener = event.target.closest('[data-open-modal]')
   if (opener) {
      event.preventDefault()
      openModal(opener.dataset.openModal)
      return
   }

   const closer = event.target.closest('[data-close-modal]')
   if (closer) {
      closeModal(closer.closest('.modal'))
      return
   }

   if (event.target.classList.contains('modal')) closeModal(event.target)
})

document.addEventListener('keydown', event => {
   if (event.key !== 'Escape') return
   const modal = $('.modal.is-open')
   if (modal) closeModal(modal)
})

/*=============== DECORATIVE BARS ===============*/
$$('[data-bars]').forEach(el => {
   const count = Number(el.dataset.bars) || 14
   const fragment = document.createDocumentFragment()
   for (let i = 0; i < count; i++) {
      const bar = document.createElement('i')
      const height = 24 + Math.round(Math.abs(Math.sin(i * 1.7 + 0.6)) * 62) + (i % 4) * 4
      bar.style.setProperty('--h', `${Math.min(height, 96)}%`)
      bar.style.setProperty('--d', `${(i % 7) * 0.08}s`)
      fragment.appendChild(bar)
   }
   el.replaceChildren(fragment)
})

/*=============== SPEECH PREVIEWS ===============*/
let activeSpeechButton = null
let activeUtterance = null

const stopSpeech = () => {
   if ('speechSynthesis' in window) window.speechSynthesis.cancel()
   if (activeSpeechButton) {
      activeSpeechButton.classList.remove('is-playing')
      const host = activeSpeechButton.closest('[data-speakable]')
      if (host) host.classList.remove('is-playing')
      const icon = activeSpeechButton.querySelector('i')
      if (icon && activeSpeechButton.dataset.iconClass) {
         icon.className = activeSpeechButton.dataset.iconClass
      } else if (activeSpeechButton.dataset.icon) {
         activeSpeechButton.innerHTML = activeSpeechButton.dataset.icon
      }
   }
   activeSpeechButton = null
   activeUtterance = null
}

const speakText = (button, text) => {
   if (!text || !text.trim()) {
      showToast('Add a line of dialogue first.', 'error')
      return
   }

   const isSame = activeSpeechButton === button
   stopSpeech()
   if (isSame) return

   const utterance = new SpeechSynthesisUtterance(text.trim())
   utterance.lang = button.dataset.lang || 'en-US'
   utterance.pitch = Number(button.dataset.pitch) || 1
   utterance.rate = Number(button.dataset.rate) || 1

   const icon = button.querySelector('i')
   if (icon) {
      button.dataset.iconClass = icon.className
      icon.className = 'ri-stop-fill'
   } else {
      button.dataset.icon = button.innerHTML
      button.innerHTML = '<i class="ri-stop-fill" aria-hidden="true"></i>'
   }
   button.classList.add('is-playing')
   const host = button.closest('[data-speakable]')
   if (host) host.classList.add('is-playing')

   activeSpeechButton = button
   activeUtterance = utterance

   utterance.onend = () => {
      if (activeSpeechButton === button) stopSpeech()
   }
   utterance.onerror = () => {
      if (activeSpeechButton === button) stopSpeech()
   }

   if (!('speechSynthesis' in window)) {
      setTimeout(() => {
         if (activeSpeechButton === button) stopSpeech()
      }, Math.min(6000, 900 + text.length * 45))
      return
   }

   window.speechSynthesis.speak(utterance)
}

document.addEventListener('click', event => {
   const button = event.target.closest('.js-speak')
   if (!button) return
   const text = button.dataset.text || ''
   speakText(button, text)
})

window.addEventListener('pagehide', stopSpeech)

/*=============== AUTH PAGE ===============*/
const authTabs = $$('[data-auth-tab]')
const authPanes = $$('[data-auth-pane]')

if (authTabs.length && authPanes.length) {
   const setAuthTab = tab => {
      authTabs.forEach(button => {
         const active = button.dataset.authTab === tab
         button.classList.toggle('is-active', active)
         button.setAttribute('aria-selected', String(active))
      })
      authPanes.forEach(pane => {
         const active = pane.dataset.authPane === tab
         pane.classList.toggle('is-active', active)
         pane.hidden = !active
      })
   }

   authTabs.forEach(tab => tab.addEventListener('click', () => setAuthTab(tab.dataset.authTab)))

   $$('[data-auth-switch]').forEach(link => {
      link.addEventListener('click', event => {
         event.preventDefault()
         setAuthTab(link.dataset.authSwitch)
      })
   })

   const signinForm = $('#signin-form')
   const signupForm = $('#signup-form')

   if (signinForm) {
      const email = $('#signin-email')
      const password = $('#signin-password')

      ;[email, password].forEach(input => input.addEventListener('input', () => clearFieldError(input)))

      signinForm.addEventListener('submit', event => {
         event.preventDefault()
         let valid = true

         if (!isEmail(email.value)) {
            markFieldError(email, 'Enter a valid email address.')
            valid = false
         }
         if (password.value.length < MIN_PASSWORD) {
            markFieldError(password, 'Passwords need at least 8 characters.')
            valid = false
         }
         if (!valid) {
            showToast('Check the highlighted fields.', 'error')
            return
         }

         const account = findAccount(email.value)
         const stored = getUser()
         const address = email.value.trim()
         const profile = {
            name: account ? account.name : stored.email.toLowerCase() === address.toLowerCase()
               ? stored.name
               : titleCase(address.split('@')[0]),
            email: address
         }
         if (account?.plan) profile.plan = account.plan

         const submit = signinForm.querySelector('button[type="submit"]')
         submit.disabled = true
         submit.textContent = 'Signing in…'

         setTimeout(() => {
            signInAs(profile, `Welcome back, ${firstNameOf(profile.name)}.`)
         }, 600)
      })
   }

   if (signupForm) {
      const name = $('#signup-name')
      const email = $('#signup-email')
      const password = $('#signup-password')

      ;[name, email, password].forEach(input => input.addEventListener('input', () => clearFieldError(input)))

      signupForm.addEventListener('submit', event => {
         event.preventDefault()
         let valid = true

         if (name.value.trim().length < 2) {
            markFieldError(name, 'Tell us what to call you.')
            valid = false
         }
         if (!isEmail(email.value)) {
            markFieldError(email, 'Enter a valid email address.')
            valid = false
         }
         if (password.value.length < MIN_PASSWORD) {
            markFieldError(password, 'Use at least 8 characters.')
            valid = false
         }
         if (!valid) {
            showToast('Check the highlighted fields.', 'error')
            return
         }

         const submit = signupForm.querySelector('button[type="submit"]')
         submit.disabled = true
         submit.textContent = 'Creating studio…'

         setTimeout(() => {
            const profile = { name: name.value.trim(), email: email.value.trim(), plan: 'Creator' }
            createAccount({ ...profile, password: password.value })
            signInAs(profile, 'Your studio is ready. Let’s make something.')
         }, 700)
      })
   }

   $$('[data-forgot]').forEach(link => {
      link.addEventListener('click', event => {
         event.preventDefault()
         const address = $('#signin-email')?.value.trim() || 'your email'
         showToast(`Reset link sent to ${address}.`)
      })
   })
}

/*=============== LOGIN PAGE ===============*/
const loginForm = $('#login-form')

if (loginForm) {
   const email = $('#login-email')
   const password = $('#login-password')
   const remember = $('#login-remember')
   const formAlert = $('#login-alert')
   const hint = $('#login-hint')
   const submit = loginForm.querySelector('button[type="submit"]')

   const seeded = new URLSearchParams(window.location.search).get('email')
   const remembered = store.get(REMEMBER_KEY, '')

   if (seeded && isEmail(seeded)) {
      email.value = seeded.trim()
   } else if (remembered) {
      email.value = remembered
      remember.checked = true
   }
   if (email.value) password.focus()

   const syncHint = () => {
      const account = isEmail(email.value) ? findAccount(email.value) : null
      hint.hidden = !account
      if (account) hint.textContent = `Found your studio: ${account.name} · ${account.plan} plan`
   }
   syncHint()

   ;[email, password].forEach(input => input.addEventListener('input', () => {
      clearFieldError(input)
      showFormAlert(formAlert, '')
   }))
   email.addEventListener('input', syncHint)

   loginForm.addEventListener('submit', event => {
      event.preventDefault()
      let valid = true

      if (!isEmail(email.value)) {
         markFieldError(email, 'Enter a valid email address.')
         valid = false
      }
      if (!password.value) {
         markFieldError(password, 'Enter your password.')
         valid = false
      }
      if (!valid) {
         showFormAlert(formAlert, 'Check the highlighted fields.')
         return
      }

      const address = email.value.trim()
      const account = findAccount(address)

      if (!account && address.toLowerCase() !== DEFAULT_USER.email) {
         markFieldError(email, 'No studio uses that email yet.')
         showFormAlert(formAlert, 'We could not find that studio.', {
            href: `register.html?email=${encodeURIComponent(address)}`,
            text: 'Create one now'
         })
         return
      }

      if (account && account.pass !== demoHash(password.value)) {
         markFieldError(password, 'That password does not match this studio.')
         showFormAlert(formAlert, 'Wrong password. Try again, or reset it.')
         return
      }

      store.set(REMEMBER_KEY, remember.checked ? address : '')

      submit.disabled = true
      submit.innerHTML = '<i class="ri-loader-4-line" aria-hidden="true"></i> Signing in…'

      const profile = account
         ? { name: account.name, email: account.email, plan: account.plan }
         : { ...DEFAULT_USER }

      setTimeout(() => signInAs(profile, `Welcome back, ${firstNameOf(profile.name)}.`), 600)
   })

   $('#demo-studio').addEventListener('click', () => {
      signInAs({ ...DEFAULT_USER }, 'Demo studio unlocked — everything here is sample data.')
   })

   const resetModal = $('#reset-modal')
   const resetForm = $('#reset-form')
   const resetEmail = $('#reset-email')

   $('[data-open-modal="reset-modal"]').addEventListener('click', () => {
      if (isEmail(email.value)) resetEmail.value = email.value.trim()
   })

   resetEmail.addEventListener('input', () => clearFieldError(resetEmail))

   resetForm.addEventListener('submit', event => {
      event.preventDefault()
      if (!isEmail(resetEmail.value)) {
         markFieldError(resetEmail, 'Enter a valid email address.')
         return
      }
      closeModal(resetModal)
      showToast(`Reset link sent to ${resetEmail.value.trim()}.`)
   })
}

/*=============== REGISTER PAGE ===============*/
const registerForm = $('#register-form')

if (registerForm) {
   const name = $('#reg-name')
   const email = $('#reg-email')
   const password = $('#reg-password')
   const confirm = $('#reg-confirm')
   const terms = $('#reg-terms')
   const formAlert = $('#register-alert')
   const meter = $('#pw-strength')
   const bars = $$('.pw-meter i', meter)
   const label = $('.pw-label', meter)
   const submit = registerForm.querySelector('button[type="submit"]')

   const seeded = new URLSearchParams(window.location.search).get('email')
   if (seeded && isEmail(seeded)) email.value = seeded.trim()

   const paintStrength = () => {
      const { rules, score, label: text } = passwordScore(password.value)
      bars.forEach((bar, index) => bar.classList.toggle('is-on', index < score))
      meter.dataset.score = String(score)
      label.textContent = text
      $$('.pw-rules li', registerForm).forEach(rule => {
         const met = rules[rule.dataset.rule]
         rule.classList.toggle('is-met', met)
         rule.querySelector('i').className = met
            ? 'ri-checkbox-circle-fill'
            : 'ri-checkbox-blank-circle-line'
      })
   }

   ;[name, email, password, confirm].forEach(input => input.addEventListener('input', () => {
      clearFieldError(input)
      showFormAlert(formAlert, '')
   }))
   password.addEventListener('input', paintStrength)
   paintStrength()

   registerForm.addEventListener('submit', event => {
      event.preventDefault()
      let valid = true

      if (name.value.trim().length < 2) {
         markFieldError(name, 'Tell us what to call you.')
         valid = false
      }
      if (!isEmail(email.value)) {
         markFieldError(email, 'Enter a valid email address.')
         valid = false
      } else if (findAccount(email.value)) {
         markFieldError(email, 'A studio already uses that email.')
         showFormAlert(formAlert, 'That email already has a studio.', {
            href: `login.html?email=${encodeURIComponent(email.value.trim())}`,
            text: 'Sign in instead'
         })
         valid = false
      }
      if (password.value.length < MIN_PASSWORD) {
         markFieldError(password, 'Use at least 8 characters.')
         valid = false
      }
      if (confirm.value !== password.value || !confirm.value) {
         markFieldError(confirm, 'Both passwords need to match.')
         valid = false
      }
      if (!terms.checked) {
         showFormAlert(formAlert, 'Tick the terms to finish creating your studio.')
         valid = false
      }
      if (!valid) {
         showToast('Check the highlighted fields.', 'error')
         return
      }

      const plan = registerForm.querySelector('input[name="plan"]:checked').value

      submit.disabled = true
      submit.innerHTML = '<i class="ri-loader-4-line" aria-hidden="true"></i> Opening your studio…'

      setTimeout(() => {
         createAccount({
            name: name.value.trim(),
            email: email.value.trim(),
            password: password.value,
            plan
         })
         signInAs(
            { name: name.value.trim(), email: email.value.trim(), plan },
            'Your studio is ready. Let’s make something.'
         )
      }, 700)
   })
}

/*=============== COVER ART BUILDER ===============*/
const hashSeed = value => [...value].reduce((total, char) => (total * 31 + char.charCodeAt(0)) % 100003, 7)

const barHeights = (seed, count) => Array.from({ length: count }, (_, index) => {
   const wave = Math.abs(Math.sin(seed + index * 1.6)) * 58
   const jitter = (seed * (index + 3)) % 22
   return Math.round(Math.min(22 + wave + jitter, 96))
})

const createCover = ({ variant = 'bars', palette = 'c-sun', letter = 'V', tag = '' }) => {
   const cover = document.createElement('div')
   cover.className = `cover cover--${variant} ${palette}`

   const add = (className, parent = cover) => {
      const span = document.createElement('span')
      span.className = className
      parent.appendChild(span)
      return span
   }

   const addWave = (count, seed) => {
      const wave = add('cover__wave')
      barHeights(seed, count).forEach(height => {
         const bar = document.createElement('i')
         bar.style.setProperty('--h', `${height}%`)
         wave.appendChild(bar)
      })
      wave.setAttribute('aria-hidden', 'true')
   }

   const seed = hashSeed(`${palette}-${variant}-${letter}`)

   if (variant === 'disc') {
      add('cover__disc')
      add('cover__letter').textContent = (letter || 'V').toUpperCase()
   } else if (variant === 'rings') {
      add('cover__rings')
      add('cover__core')
   } else if (variant === 'wave') {
      add('cover__line')
      addWave(12, seed)
   } else if (variant === 'grid') {
      add('cover__grid')
      add('cover__core')
   } else if (variant === 'type') {
      add('cover__letter').textContent = (letter || 'V').toUpperCase()
      add('cover__line')
   } else {
      add('cover__line')
      addWave(13, seed)
   }

   if (tag) {
      const badge = add('cover__tag')
      const icon = document.createElement('i')
      icon.className = 'ri-headphones-line'
      icon.setAttribute('aria-hidden', 'true')
      badge.append(icon, document.createTextNode(tag))
   }

   return cover
}

const renderCover = (container, spec) => {
   const fresh = createCover(spec)
   container.className = fresh.className
   container.replaceChildren(...fresh.childNodes)
}

/*=============== VOICE CLONING PAGE ===============*/
const cloneWizard = $('#clone-wizard')

if (cloneWizard) {
   const nameInput = $('#voice-name')
   const languageSelect = $('#voice-language')
   const categorySelect = $('#voice-category')
   const consentBox = $('#clone-consent')
   const startButton = $('#clone-start')
   const requirement = $('#clone-requirement')
   const sampleBadge = $('#sample-badge')
   const micError = $('#mic-error')
   const uploadError = $('#upload-error')
   const recToggle = $('#rec-toggle')
   const recMeter = $('#rec-meter')
   const recTime = $('#rec-time')
   const recStatus = $('#rec-status')
   const recordSample = $('#record-sample')
   const uploadSample = $('#upload-sample')
   const dropZone = $('#drop-zone')
   const uploadInput = $('#upload-input')
   const cloneGrid = $('#clone-grid')
   const cloneEmpty = $('#clone-empty')
   const modal = $('#clone-modal')

   const SCRIPTS = [
      'The morning market opens late, and the coffee is already gone.',
      'I kept the receipt, the map, and every promise we made on the ferry.',
      'Sixteen bars of tape, one take, and a room full of people holding their breath.',
      'Somewhere between the second verse and the sunrise, the song started working.',
      'She counts the steps to the door every night, and every night she stops at three.'
   ]

   let scriptIndex = 0
   let captured = null
   let rec = null
   let training = false

   const supportsRecording = Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== 'undefined'

   /*---------- Capture state ----------*/
   const showFieldError = (node, message) => {
      if (!node) return
      node.textContent = message
      node.classList.add('is-visible')
   }

   const clearFieldError = node => {
      if (!node) return
      node.classList.remove('is-visible')
   }

   const formatSize = bytes => (bytes >= 1024 * 1024
      ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
      : `${Math.max(1, Math.round(bytes / 1024))} KB`)

   const setBadge = () => {
      if (!sampleBadge) return
      if (captured) {
         const length = captured.seconds ? ` · ${formatClock(captured.seconds)}` : ''
         sampleBadge.innerHTML = '<i class="ri-checkbox-circle-fill" aria-hidden="true"></i> Sample ready'
         sampleBadge.append(document.createTextNode(`${length}`))
      } else {
         sampleBadge.innerHTML = '<i class="ri-mic-line" aria-hidden="true"></i> No sample yet'
      }
   }

   const paintSample = (host, source, label, icon) => {
      if (!host) return
      if (!captured || captured.source !== source) {
         host.hidden = true
         host.replaceChildren()
         return
      }

      const src = captured.objectUrl || captured.audio
      const head = document.createElement('div')
      head.className = 'sample__head'

      const labelNode = document.createElement('span')
      labelNode.className = 'sample__label'
      labelNode.innerHTML = `<i class="${icon}" aria-hidden="true"></i>`
      const text = document.createElement('span')
      text.textContent = `${label}${captured.seconds ? ` · ${formatClock(captured.seconds)}` : ''}${captured.fileSize ? ` · ${formatSize(captured.fileSize)}` : ''}`
      labelNode.append(text)

      const clear = document.createElement('button')
      clear.type = 'button'
      clear.className = 'link-btn'
      clear.dataset.clearSample = ''
      clear.innerHTML = '<i class="ri-delete-bin-line" aria-hidden="true"></i> Remove'

      head.append(labelNode, clear)

      const player = document.createElement('audio')
      player.controls = true
      player.src = src
      player.setAttribute('aria-label', `Listen to the ${label} sample`)

      host.replaceChildren(head, player)
      host.hidden = false
   }

   const paintSamples = () => {
      paintSample(recordSample, 'record', 'Recorded sample', 'ri-mic-fill')
      paintSample(uploadSample, 'upload', captured?.fileName || 'Uploaded sample', 'ri-file-music-line')
      setBadge()
      syncGate()
   }

   const clearCaptured = () => {
      releaseUrl(captured?.objectUrl)
      captured = null
      paintSamples()
   }

   const requirementState = () => {
      const missing = []
      if (!captured) missing.push('a sample')
      const name = nameInput.value.trim()
      if (name.length < 2) missing.push('a voice name')
      else if (!isVoiceNameFree(name)) missing.push('a name you have not used yet')
      if (!consentBox.checked) missing.push('permission confirmation')

      const { used, limit } = voiceSlotUsage()
      if (limit !== null && used >= limit) missing.push('a free voice slot')

      return missing
   }

   function syncGate() {
      const missing = requirementState()
      startButton.disabled = missing.length > 0 || training
      requirement.textContent = missing.length
         ? `Still needed: ${missing.join(', ')}.`
         : 'Ready. Cloning takes about ten seconds.'
   }

   /*---------- Tabs ----------*/
   const captureTabs = $$('[data-capture-tab]')

   const setCaptureTab = tab => {
      captureTabs.forEach(button => {
         const active = button.dataset.captureTab === tab
         button.classList.toggle('is-active', active)
         button.setAttribute('aria-selected', String(active))
      })
      $$('[data-capture-pane]').forEach(pane => {
         const active = pane.dataset.capturePane === tab
         pane.classList.toggle('is-active', active)
         pane.hidden = !active
      })
   }

   captureTabs.forEach(button => button.addEventListener('click', () => setCaptureTab(button.dataset.captureTab)))

   $('#script-swap')?.addEventListener('click', () => {
      scriptIndex = (scriptIndex + 1) % SCRIPTS.length
      $('#record-script').textContent = SCRIPTS[scriptIndex]
   })

   /*---------- Recording ----------*/
   const METER_BARS = 28

   if (recMeter) {
      const fragment = document.createDocumentFragment()
      for (let i = 0; i < METER_BARS; i++) fragment.appendChild(document.createElement('i'))
      recMeter.replaceChildren(fragment)
   }

   const setMeter = (levels = null) => {
      $$('i', recMeter).forEach((bar, index) => {
         const height = levels ? 12 + Math.round(levels[index % levels.length] * 88) : 12
         bar.style.height = `${Math.min(height, 100)}%`
      })
      recMeter.classList.toggle('is-live', Boolean(levels))
   }

   const pickMime = () => ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
      .find(type => typeof MediaRecorder.isTypeSupported === 'function' && MediaRecorder.isTypeSupported(type)) || ''

   if (!supportsRecording) {
      recStatus.textContent = 'Recording needs microphone support. Use the Upload tab instead.'
      recToggle.disabled = true
      captureTabs.forEach(button => {
         if (button.dataset.captureTab === 'record') button.disabled = true
      })
      setCaptureTab('upload')
   }

   const tickRecording = () => {
      const seconds = (Date.now() - rec.startedAt) / 1000
      recTime.textContent = formatClock(seconds)
      if (seconds >= REC_MAX_SECONDS) stopRecording(true)
   }

   const drawLevels = () => {
      if (!rec) return
      rec.analyser.getByteTimeDomainData(rec.waveform)
      const bars = $$('i', recMeter)
      const per = Math.floor(rec.waveform.length / bars.length) || 1
      const levels = bars.map((_, index) => {
         let peak = 0
         for (let i = 0; i < per; i++) {
            const value = Math.abs(rec.waveform[index * per + i] - 128) / 128
            peak = Math.max(peak, value)
         }
         return Math.min(peak * 2.2, 1)
      })
      setMeter(levels)
      rec.frame = requestAnimationFrame(drawLevels)
   }

   async function startRecording() {
      recToggle.disabled = true
      recStatus.textContent = 'Requesting the microphone…'
      clearFieldError(micError)

      try {
         const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
         const AudioContextClass = window.AudioContext || window.webkitAudioContext
         const ctx = new AudioContextClass()
         const source = ctx.createMediaStreamSource(stream)
         const analyser = ctx.createAnalyser()
         analyser.fftSize = 512
         source.connect(analyser)

         const recorder = new MediaRecorder(stream, pickMime() ? { mimeType: pickMime() } : undefined)
         const chunks = []
         recorder.ondataavailable = event => {
            if (event.data && event.data.size) chunks.push(event.data)
         }
         recorder.onstop = () => finishRecording(chunks)

         recorder.start()
         rec = { stream, ctx, analyser, recorder, chunks, startedAt: Date.now(), timer: null, frame: null, waveform: new Uint8Array(analyser.fftSize) }

         recToggle.disabled = false
         recToggle.classList.add('is-recording')
         recToggle.setAttribute('aria-label', 'Stop recording')
         recToggle.querySelector('i').className = 'ri-stop-fill'
         recStatus.textContent = 'Recording. Read the script at your normal pace.'
         recMeter.classList.add('is-live')
         rec.timer = setInterval(tickRecording, 250)
         drawLevels()
      } catch {
         recToggle.disabled = false
         recStatus.textContent = 'Tap the mic and start reading. Minimum 10 seconds.'
         showFieldError(micError, 'The microphone was blocked. Allow mic access in your browser, or upload a file instead.')
      }
   }

   function stopRecording(auto = false) {
      if (!rec) return
      const seconds = (Date.now() - rec.startedAt) / 1000
      clearInterval(rec.timer)
      cancelAnimationFrame(rec.frame)
      rec.stream.getTracks().forEach(track => track.stop())
      rec.recorder.stop()

      const context = rec.ctx
      if (context && context.state !== 'closed') context.close()

      rec.seconds = seconds
      rec = { ...rec, stopping: true, seconds }
      setMeter()
      recToggle.classList.remove('is-recording')
      recToggle.querySelector('i').className = 'ri-mic-fill'
      recToggle.setAttribute('aria-label', 'Start recording')
      recStatus.textContent = auto
         ? `Reached the ${Math.round(REC_MAX_SECONDS)} second limit. Processing…`
         : 'Processing your sample…'
   }

   async function finishRecording(chunks) {
      const seconds = rec?.seconds || 0
      const state = rec
      rec = null
      recTime.textContent = formatClock(Math.max(1, seconds))

      if (state?.stopping !== true) return

      if (seconds < SAMPLE_MIN_SECONDS) {
         showFieldError(micError, `That was ${Math.round(seconds)} seconds. Record at least ${SAMPLE_MIN_SECONDS} for a usable clone.`)
         recStatus.textContent = 'Tap the mic and start reading again.'
         return
      }

      clearFieldError(micError)
      const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' })
      const objectUrl = URL.createObjectURL(blob)
      const audio = blob.size <= PERSIST_MAX_BYTES ? await blobToDataUrl(blob) : null

      captured = {
         source: 'record',
         seconds,
         fileSize: blob.size,
         fileName: null,
         objectUrl,
         audio
      }
      recStatus.textContent = 'Nice. Add a name below and start the clone.'
      paintSamples()
   }

   recToggle?.addEventListener('click', () => {
      if (!rec) return startRecording()
      stopRecording(false)
   })

   /*---------- Upload ----------*/
   const AUDIO_PATTERN = /\.(mp3|wav|m4a|aac|ogg|oga|flac|weba|webm)$/i

   async function handleFile(file) {
      clearFieldError(uploadError)

      if (!file) return
      if (!file.type.startsWith('audio/') && !AUDIO_PATTERN.test(file.name)) {
         showFieldError(uploadError, 'That is not an audio file. Use MP3, WAV, M4A, OGG or FLAC.')
         return
      }
      if (file.size > UPLOAD_MAX_BYTES) {
         showFieldError(uploadError, `That file is ${formatSize(file.size)}. Keep samples under ${formatSize(UPLOAD_MAX_BYTES)}.`)
         return
      }

      releaseUrl(captured?.objectUrl)
      captured = null

      const objectUrl = URL.createObjectURL(file)
      const seconds = await readAudioDuration(objectUrl)

      if (seconds !== null && seconds < SAMPLE_MIN_SECONDS) {
         URL.revokeObjectURL(objectUrl)
         showFieldError(uploadError, `That clip is ${formatClock(seconds)}. Use at least ${SAMPLE_MIN_SECONDS} seconds of steady speech.`)
         paintSamples()
         return
      }
      if (seconds !== null && seconds > UPLOAD_MAX_SECONDS) {
         URL.revokeObjectURL(objectUrl)
         showFieldError(uploadError, `That clip is ${formatClock(seconds)}. Keep it under ${formatClock(UPLOAD_MAX_SECONDS)}.`)
         paintSamples()
         return
      }

      const audio = file.size <= PERSIST_MAX_BYTES ? await blobToDataUrl(file) : null
      captured = {
         source: 'upload',
         seconds,
         fileSize: file.size,
         fileName: file.name,
         objectUrl,
         audio
      }
      paintSamples()
   }

   uploadInput?.addEventListener('change', () => {
      const file = uploadInput.files?.[0]
      handleFile(file)
      uploadInput.value = ''
   })

   if (dropZone) {
      const markDrag = on => event => {
         event.preventDefault()
         dropZone.classList.toggle('is-drag', on)
      }
      ;['dragenter', 'dragover'].forEach(type => dropZone.addEventListener(type, markDrag(true)))
      ;['dragleave', 'drop'].forEach(type => dropZone.addEventListener(type, markDrag(false)))
      dropZone.addEventListener('drop', event => {
         handleFile(event.dataTransfer?.files?.[0])
      })
   }

   cloneWizard.addEventListener('click', event => {
      if (event.target.closest('[data-clear-sample]')) clearCaptured()
   })

   /*---------- Details gate ----------*/
   ;[nameInput, languageSelect, categorySelect, consentBox].forEach(node => {
      node?.addEventListener('input', () => {
         if (nameInput.value.trim().length >= 2 && !isVoiceNameFree(nameInput.value)) {
            showFieldError(nameInput.closest('.field').querySelector('.field__error'), 'You already have a voice with that name.')
         } else {
            clearFieldError(nameInput.closest('.field').querySelector('.field__error'))
         }
         syncGate()
      })
      node?.addEventListener('change', syncGate)
   })

   /*---------- Library ----------*/
   const slotRows = () => {
      const { used, limit } = voiceSlotUsage()
      const unlimited = limit === null

      $$('[data-voice-slots]').forEach(node => { node.textContent = `${used} / ${unlimited ? 'Unlimited' : limit}` })
      $$('[data-voice-meter] i').forEach(node => {
         node.style.setProperty('--v', unlimited ? '100%' : `${Math.min(100, (used / limit) * 100)}%`)
      })

      const note = $('[data-voice-slots-note]')
      if (note) {
         if (unlimited) note.textContent = `Unlimited clones on the ${getUser().plan} plan.`
         else if (used >= limit) note.textContent = 'Every slot is taken. Delete a voice or upgrade for more.'
         else {
            const free = limit - used
            note.textContent = `${free} slot${free === 1 ? '' : 's'} left on the ${getUser().plan} plan.`
         }
      }

      const count = $('[data-voice-count]')
      if (count) count.textContent = `${used} voice${used === 1 ? '' : 's'}`
   }

   const buildVoiceCard = voice => {
      const sample = clonedSample(voice)
      const used = voiceUsage(voice.name)

      const card = document.createElement('article')
      card.className = 'clone-card'
      card.dataset.voiceId = voice.id

      const cover = createCover({ ...coverForVoice(voice), tag: '' })
      cover.classList.add('clone-card__cover')

      const body = document.createElement('div')
      body.className = 'clone-card__body'

      const top = document.createElement('div')
      top.className = 'clone-card__top'
      const name = document.createElement('h3')
      name.className = 'clone-card__name'
      name.textContent = voice.name
      const badge = document.createElement('span')
      badge.className = 'chip chip--clone'
      badge.textContent = voice.visibility === 'market' ? 'Listed' : 'Cloned'
      top.append(name, badge)

      const meta = document.createElement('p')
      meta.className = 'clone-card__meta'
      meta.textContent = `${sourceLabel(voice)}${voice.seconds ? ` · ${formatClock(voice.seconds)}` : ''} · ${voice.language} · ${voice.category}`

      const detail = document.createElement('p')
      detail.className = 'clone-card__file'
      const parts = [`Added ${formatDate(voice.createdAt)}`]
      if (voice.fileName) parts.push(voice.fileName)
      parts.push(used ? `Used in ${used} episode${used === 1 ? '' : 's'}` : 'Not cast yet')
      detail.textContent = parts.join(' · ')

      const actions = document.createElement('div')
      actions.className = 'clone-card__actions'

      const play = document.createElement('button')
      play.type = 'button'
      play.className = 'play-btn'
      play.setAttribute('aria-label', sample ? `Play the ${voice.name} sample` : `Preview ${voice.name}`)
      play.innerHTML = '<i class="ri-play-fill" aria-hidden="true"></i>'
      if (sample) {
         play.dataset.voicePlay = voice.id
      } else {
         play.classList.add('js-speak')
         play.dataset.text = `This is ${voice.name}. Your own voice, ready to cast.`
      }

      const edit = document.createElement('button')
      edit.type = 'button'
      edit.className = 'link-btn'
      edit.dataset.voiceEdit = voice.id
      edit.innerHTML = '<i class="ri-edit-2-line" aria-hidden="true"></i> Rename'

      const del = document.createElement('button')
      del.type = 'button'
      del.className = 'link-btn'
      del.dataset.voiceDelete = voice.id
      del.innerHTML = '<i class="ri-delete-bin-line" aria-hidden="true"></i> Delete'

      actions.append(play, edit, del)
      body.append(top, meta, detail, actions)
      card.append(cover, body)
      return card
   }

   const renderLibrary = () => {
      const voices = getClonedVoices()
      if (cloneGrid) cloneGrid.replaceChildren(...voices.map(buildVoiceCard))
      cloneEmpty?.classList.toggle('is-visible', !voices.length)
      slotRows()
      syncGate()
   }

   /*---------- Training run ----------*/
   const stages = $$('[data-clone-stage]')
   const cloneBar = $('#clone-bar')
   const cloneLoading = $('#clone-loading')
   const cloneSuccess = $('#clone-success')

   const resetCloneModal = () => {
      cloneLoading?.classList.remove('is-hidden')
      cloneSuccess?.classList.remove('is-active')
      if (cloneBar) cloneBar.style.width = '0%'
      $$('.render-stage', modal).forEach(stage => {
         stage.classList.remove('is-active', 'is-done')
         const icon = stage.querySelector('i')
         if (icon) icon.className = 'ri-loader-4-line'
      })
   }

   const completeClone = voice => {
      const outcome = persistClonedVoice(voice)
      if (voice.sessionUrl) sampleCache.set(voice.id, voice.sessionUrl)

      if (outcome === 'failed') {
         showToast('Could not save this voice — browser storage is full.', 'error')
      } else {
         showToast(outcome === 'slim'
            ? `${voice.name} is saved. The sample was too large to keep, so previews use the browser voice.`
            : `${voice.name} is in your library and your cast list.`)
      }

      renderLibrary()

      const coverHost = $('#clone-success-cover')
      if (coverHost) renderCover(coverHost, coverForVoice(voice))
      $('#clone-success-name').textContent = voice.name
      $('#clone-success-meta').textContent = `${sourceLabel(voice)}${voice.seconds ? ` · ${formatClock(voice.seconds)}` : ''} · ${voice.language} · ${voice.category}`

      cloneLoading?.classList.add('is-hidden')
      cloneSuccess?.classList.add('is-active')
      training = false
      syncGate()
   }

   const runClone = voice => {
      training = true
      syncGate()

      $$('.render-stage', modal).forEach(stage => {
         stage.classList.remove('is-active', 'is-done')
         const icon = stage.querySelector('i')
         if (icon) icon.className = 'ri-loader-4-line'
      })
      if (cloneBar) cloneBar.style.width = '8%'

      stages.forEach((stage, index) => {
         setTimeout(() => {
            stages.forEach((item, itemIndex) => {
               if (itemIndex < index) {
                  item.classList.remove('is-active')
                  item.classList.add('is-done')
                  const icon = item.querySelector('i')
                  if (icon) icon.className = 'ri-checkbox-circle-fill'
               }
            })
            stage.classList.add('is-active')
            if (cloneBar) cloneBar.style.width = `${18 + (index / stages.length) * 70}%`
         }, index * 720)
      })

      setTimeout(() => {
         if (cloneBar) cloneBar.style.width = '100%'
         stages.forEach(stage => {
            stage.classList.remove('is-active')
            stage.classList.add('is-done')
            const icon = stage.querySelector('i')
            if (icon) icon.className = 'ri-checkbox-circle-fill'
         })
         setTimeout(() => completeClone(voice), 400)
      }, stages.length * 720 + 280)
   }

   startButton?.addEventListener('click', () => {
      if (!requirementState().length) {
         if (training) return

         const total = getClonedVoices().length
         const voice = {
            id: `vc-${Date.now().toString(36)}`,
            name: nameInput.value.trim(),
            language: languageSelect.value,
            category: categorySelect.value,
            visibility: $('input[name="visibility"]:checked')?.value || 'private',
            source: captured.source,
            seconds: captured.seconds,
            fileName: captured.fileName,
            fileSize: captured.fileSize,
            audio: captured.audio,
            sessionUrl: captured.audio ? null : captured.objectUrl,
            createdAt: new Date().toISOString(),
            palette: CLONE_PALETTES[total % CLONE_PALETTES.length],
            variant: CLONE_VARIANTS[total % CLONE_VARIANTS.length]
         }

         resetCloneModal()
         openModal('clone-modal')
         runClone(voice)
         return
      }

      if (!captured) showFieldError(micError, 'Record or upload a sample before cloning.')
      if (nameInput.value.trim().length < 2) showFieldError(nameInput.closest('.field').querySelector('.field__error'), 'Give this voice a name (2+ characters).')
      syncGate()
   })

   $('#clone-another')?.addEventListener('click', () => {
      closeModal(modal)
      clearCaptured()
      nameInput.value = ''
      consentBox.checked = false
      clearFieldError(micError)
      clearFieldError(uploadError)
      clearFieldError(nameInput.closest('.field').querySelector('.field__error'))
      syncGate()
      nameInput.focus()
   })

   /*---------- Rename + delete ----------*/
   let editingId = null
   let deletingId = null

   const editFieldError = $('#voice-edit-modal .field__error')

   document.addEventListener('click', event => {
      const edit = event.target.closest('[data-voice-edit]')
      if (edit) {
         const voice = findClonedVoice(edit.dataset.voiceEdit)
         if (!voice) return
         editingId = voice.id
         $('#edit-name').value = voice.name
         $('#edit-language').value = voice.language
         $('#edit-category').value = voice.category
         clearFieldError(editFieldError)
         openModal('voice-edit-modal')
         setTimeout(() => $('#edit-name').focus(), 120)
         return
      }

      const remove = event.target.closest('[data-voice-delete]')
      if (remove) {
         const voice = findClonedVoice(remove.dataset.voiceDelete)
         if (!voice) return
         deletingId = voice.id
         $('[data-delete-name]').textContent = voice.name
         $('[data-delete-sample]').textContent = `${sourceLabel(voice)}${voice.seconds ? ` · ${formatClock(voice.seconds)}` : ''}`
         $('[data-delete-created]').textContent = formatDate(voice.createdAt)
         openModal('voice-delete-modal')
      }
   })

   $('#voice-edit-save')?.addEventListener('click', () => {
      const name = $('#edit-name').value.trim()
      if (name.length < 2) {
         showFieldError(editFieldError, 'Give this voice a name (2+ characters).')
         return
      }
      const others = getClonedVoices().filter(voice => voice.id !== editingId)
      if (others.some(voice => voice.name.trim().toLowerCase() === name.toLowerCase())) {
         showFieldError(editFieldError, 'You already have a voice with that name.')
         return
      }

      const previous = findClonedVoice(editingId)
      const renamed = updateClonedVoice(editingId, {
         name,
         language: $('#edit-language').value,
         category: $('#edit-category').value
      })

      if (!renamed) {
         showToast('Could not save the new name.', 'error')
         return
      }

      if (previous && previous.name !== name) {
         const cached = sampleCache.get(editingId)
         if (cached) sampleCache.set(editingId, cached)
      }

      closeModal($('#voice-edit-modal'))
      renderLibrary()
      showToast(`Renamed to ${name}.`)
   })

   $('#voice-delete-confirm')?.addEventListener('click', () => {
      const voice = findClonedVoice(deletingId)
      if (!voice) return

      if (!dropClonedVoice(voice.id)) {
         showToast('Could not delete this voice.', 'error')
         return
      }

      stopSample()
      closeModal($('#voice-delete-modal'))
      renderLibrary()
      showToast(`${voice.name} deleted. Episodes already rendered keep their audio.`)
      deletingId = null
   })

   renderLibrary()
   paintSamples()
   setCaptureTab(supportsRecording ? 'record' : 'upload')
}

/*=============== DASHBOARD ===============*/
const dashboardEpisodes = $('#dash-episodes')

if (dashboardEpisodes) {
   const custom = getUserEpisodes()

   const episodeCount = $('[data-stat-episodes]')
   if (episodeCount) episodeCount.textContent = String(12 + custom.length)

   custom.forEach(episode => {
      const row = document.createElement('article')
      row.className = 'ep'

      const cover = createCover({ ...episode.spec, tag: '' })
      cover.classList.add('ep__cover')

      const body = document.createElement('div')
      body.className = 'ep__body'

      const title = document.createElement('h3')
      title.className = 'ep__title'
      title.textContent = episode.title

      const meta = document.createElement('p')
      meta.className = 'ep__meta'
      const metaText = document.createElement('span')
      metaText.innerHTML = '<i class="ri-album-line" aria-hidden="true"></i>'
      metaText.append(document.createTextNode(`${episode.genreLabel} · ${episode.duration}`))
      const date = document.createElement('span')
      date.innerHTML = '<i class="ri-time-line" aria-hidden="true"></i>'
      date.append(document.createTextNode(formatDate(episode.createdAt)))
      meta.append(metaText, date)

      body.append(title, meta)

      const right = document.createElement('div')
      right.className = 'ep__right'

      const chip = document.createElement('span')
      chip.className = 'chip chip--ready'
      chip.textContent = 'Ready'

      const play = document.createElement('button')
      play.className = 'play-btn js-speak'
      play.type = 'button'
      play.dataset.text = episode.script || episode.title
      play.setAttribute('aria-label', `Play ${episode.title}`)
      play.innerHTML = '<i class="ri-play-fill" aria-hidden="true"></i>'

      right.append(chip, play)
      row.append(cover, body, right)
      dashboardEpisodes.prepend(row)
   })

   const miniGrid = $('#dash-mini-grid')
   if (miniGrid && custom.length) {
      custom.slice(0, 2).forEach(episode => {
         const mini = document.createElement('a')
         mini.className = 'mini'
         mini.href = 'gallery.html'
         const cover = createCover({ ...episode.spec, tag: '' })
         const title = document.createElement('span')
         title.className = 'mini__title'
         title.textContent = episode.title
         const meta = document.createElement('span')
         meta.className = 'mini__meta'
         meta.textContent = `${episode.genreLabel} · ${episode.duration}`
         mini.append(cover, title, meta)
         miniGrid.prepend(mini)
      })
   }
}

/*=============== DASHBOARD VOICE PANEL ===============*/
const dashboardSide = $('.dash-grid__side')

if (dashboardSide) {
   const voices = getClonedVoices()

   const statValue = $('[data-stat-voices]')
   if (statValue) statValue.textContent = String(3 + voices.length)

   const statMeta = $('[data-stat-voices-meta]')
   if (statMeta) {
      statMeta.textContent = voices.length
         ? `${voices.length} cloned · 3 stock voices`
         : '3 cloned · 3 stock voices'
   }

   const panel = document.createElement('section')
   panel.className = 'panel'
   panel.setAttribute('aria-labelledby', 'dash-voices-title')

   const head = document.createElement('div')
   head.className = 'panel__head'
   head.innerHTML = `
      <div>
         <h2 class="panel__title" id="dash-voices-title">Cloned voices</h2>
         <p class="panel__sub">Named samples, ready to cast.</p>
      </div>
      <a href="voices.html" class="panel__link">Voice studio <i class="ri-arrow-right-line" aria-hidden="true"></i></a>
   `

   const body = document.createElement('div')
   body.className = 'panel__body'

   if (!voices.length) {
      const empty = document.createElement('p')
      empty.className = 'panel__sub'
      empty.style.marginBottom = '0.75rem'
      empty.textContent = 'No cloned voices yet. Record or upload ten seconds of speech to get one.'
      const cta = document.createElement('a')
      cta.className = 'btn btn--soft btn--sm'
      cta.href = 'voices.html'
      cta.innerHTML = '<i class="ri-user-voice-line" aria-hidden="true"></i> Clone a voice'
      body.append(empty, cta)
   } else {
      const list = document.createElement('div')
      voices.slice(0, 4).forEach(voice => {
         const sample = clonedSample(voice)
         const row = document.createElement('div')
         row.className = 'voice-row'

         const cover = createCover({ ...coverForVoice(voice), tag: '' })
         cover.style.width = '2.4rem'

         const text = document.createElement('div')
         const name = document.createElement('span')
         name.className = 'voice-row__name'
         name.textContent = voice.name
         const meta = document.createElement('span')
         meta.className = 'voice-row__meta'
         meta.textContent = `${sourceLabel(voice)}${voice.seconds ? ` · ${formatClock(voice.seconds)}` : ''} · ${voice.category}`
         text.append(name, meta)

         const play = document.createElement('button')
         play.type = 'button'
         play.className = 'play-btn'
         play.setAttribute('aria-label', sample ? `Play the ${voice.name} sample` : `Preview ${voice.name}`)
         play.innerHTML = '<i class="ri-play-fill" aria-hidden="true"></i>'
         if (sample) play.dataset.voicePlay = voice.id
         else {
            play.classList.add('js-speak')
            play.dataset.text = `This is ${voice.name}. Your own voice, ready to cast.`
         }

         row.append(cover, text, play)
         list.append(row)
      })
      body.append(list)
   }

   panel.append(head, body)
   dashboardSide.append(panel)
}

/*=============== GALLERY ===============*/
const galleryGrid = $('#gallery-grid')

if (galleryGrid) {
   const renderGrid = $('#your-renders')
   const renderEmpty = $('#your-renders-empty')
   const emptyState = $('#gallery-empty')
   const searchInput = $('#gallery-search')
   const countLabel = $('[data-gallery-count]')
   const pills = $$('[data-gfilter]')
   const userEpisodes = getUserEpisodes()

   if (renderGrid) {
      if (!userEpisodes.length) {
         if (renderEmpty) renderEmpty.classList.add('is-visible')
      } else {
         if (renderEmpty) renderEmpty.classList.remove('is-visible')
         userEpisodes.forEach(episode => {
            const card = document.createElement('article')
            card.className = 'pod-card'
            card.dataset.genre = 'renders'
            card.dataset.search = `${episode.title} ${episode.genreLabel} ${episode.author}`.toLowerCase()
            card.dataset.speakable = ''

            const cover = createCover({ ...episode.spec, tag: 'Your render' })

            const body = document.createElement('div')
            body.className = 'pod-card__body'
            const title = document.createElement('h3')
            title.className = 'pod-card__title'
            title.textContent = episode.title
            const meta = document.createElement('p')
            meta.className = 'pod-card__meta'
            meta.textContent = `${episode.genreLabel} · ${episode.author} · ${episode.duration}`
            body.append(title, meta)

            const foot = document.createElement('div')
            foot.className = 'pod-card__foot'

            const stats = document.createElement('div')
            stats.innerHTML = `
               <span class="pod-card__stat"><i class="ri-headphone-line" aria-hidden="true"></i>${episode.plays || 0}</span>
               <span class="pod-card__stat"><i class="ri-calendar-line" aria-hidden="true"></i>${formatDate(episode.createdAt)}</span>
            `

            const play = document.createElement('button')
            play.className = 'play-btn js-speak'
            play.type = 'button'
            play.dataset.text = episode.script || episode.title
            play.setAttribute('aria-label', `Listen to ${episode.title}`)
            play.innerHTML = '<i class="ri-play-fill" aria-hidden="true"></i>'

            foot.append(stats, play)
            card.append(cover, body, foot)
            renderGrid.prepend(card)
         })
      }
   }

   const clearSearch = $('#gallery-clear')

   const applyFilters = () => {
      const active = $('.pill.is-active[data-gfilter]')?.dataset.gfilter || 'all'
      const query = (searchInput?.value || '').trim().toLowerCase()

      let total = 0

      const matches = card => {
         const genre = card.dataset.genre
         const haystack = card.dataset.search || ''
         const genreOk = active === 'all' || genre === active || (active === 'renders' && genre === 'renders')
         const searchOk = !query || haystack.includes(query)
         return genreOk && searchOk
      }

      $$('.pod-card', galleryGrid).forEach(card => {
         const visible = matches(card)
         card.hidden = !visible
         if (visible) total++
      })

      if (renderGrid) {
         $$('.pod-card', renderGrid).forEach(card => {
            const visible = active === 'all' || active === 'renders'
               ? matches(card)
               : false
            card.hidden = !visible
         })
      }

      if (countLabel) countLabel.textContent = `${total} podcast${total === 1 ? '' : 's'}`
      if (emptyState) emptyState.classList.toggle('is-visible', total === 0)
      if (clearSearch) clearSearch.hidden = !query
   }

   if (pills.length) {
      pills.forEach(pill => {
         pill.addEventListener('click', () => {
            pills.forEach(item => item.classList.toggle('is-active', item === pill))
            applyFilters()
         })
      })
   }

   if (searchInput) searchInput.addEventListener('input', applyFilters)

   if (clearSearch) {
      clearSearch.addEventListener('click', () => {
         searchInput.value = ''
         applyFilters()
         searchInput.focus()
      })
   }

   // "Your renders" pill only appears when there are renders
   const rendersPill = $('[data-gfilter="renders"]')
   if (rendersPill && !userEpisodes.length) rendersPill.hidden = true

   applyFilters()
}

/*=============== PAYMENTS ===============*/
const PLANS = {
   Starter: { price: '$0', cadence: '/forever', limit: 20, used: 18, label: 'Starter' },
   Creator: { price: '$24', cadence: '/month', limit: 60, used: 42, label: 'Creator' },
   Studio: { price: '$79', cadence: '/month', limit: 240, used: 42, label: 'Studio' }
}

const PLAN_RANK = { Starter: 0, Creator: 1, Studio: 2 }

const billingBanner = $('.billing-banner')

if (billingBanner) {
   const planCards = $$('[data-plan-card]')
   const planButtons = $$('[data-plan]')
   const planModal = $('#plan-modal')
   let pendingPlan = null

   const syncPlanUI = plan => {
      const data = PLANS[plan] || PLANS.Creator

      $$('[data-user-plan]').forEach(el => { el.textContent = `${plan} plan` })

      planCards.forEach(card => {
         const name = card.dataset.planCard
         const isCurrent = name === plan
         card.classList.toggle('is-current', isCurrent)
         const badge = card.querySelector('[data-current-badge]')
         if (badge) badge.hidden = !isCurrent

         const button = card.querySelector('[data-plan]')
         if (!button) return
         button.disabled = isCurrent
         if (isCurrent) {
            button.textContent = 'Current plan'
         } else if (PLAN_RANK[name] > PLAN_RANK[plan]) {
            button.textContent = `Upgrade to ${name}`
         } else {
            button.textContent = `Switch to ${name}`
         }
      })

      $$('[data-banner-plan]').forEach(el => { el.textContent = data.label })
      $$('[data-banner-price]').forEach(el => { el.textContent = data.price })
      $$('[data-banner-usage]').forEach(el => { el.textContent = `${data.used} of ${data.limit} min` })
      $$('[data-banner-limit]').forEach(el => { el.textContent = `${data.limit} min` })

      const meter = $('[data-banner-meter]')
      if (meter) meter.style.setProperty('--v', `${Math.min(100, (data.used / data.limit) * 100)}%`)
   }

   planButtons.forEach(button => {
      button.addEventListener('click', () => {
         if (button.disabled) return
         pendingPlan = button.dataset.plan
         const data = PLANS[pendingPlan]

         $('#plan-modal-name').textContent = `${data.label} plan`
         $('#plan-modal-price').textContent = `${data.price}${data.cadence}`
         $('#plan-modal-limit').textContent = `${data.limit} minutes of renders / month`
         $('#plan-confirm').textContent = `Confirm ${data.label} plan`
         openModal('plan-modal')
      })
   })

   const confirmPlan = $('#plan-confirm')
   if (confirmPlan) {
      confirmPlan.addEventListener('click', () => {
         if (!pendingPlan) return
         const plan = pendingPlan
         store.set(USER_KEY, { ...getUser(), plan })
         syncPlanUI(plan)
         closeModal(planModal)
         showToast(`${plan} plan is now active.`)
         pendingPlan = null
      })
   }

   syncPlanUI(getUser().plan)

   const cardForm = $('#card-form')

   if (cardForm) {
      const number = $('#card-number')
      const expiry = $('#card-exp')
      const cvc = $('#card-cvc')
      const clearFieldError = input => input.closest('.field')?.classList.remove('is-error')
      const markError = (input, message) => {
         const field = input.closest('.field')
         if (!field) return
         field.classList.add('is-error')
         const error = field.querySelector('.field__error')
         if (error) error.textContent = message
      }

      ;[number, expiry, cvc].forEach(input => input.addEventListener('input', () => clearFieldError(input)))

      number.addEventListener('input', () => {
         const digits = number.value.replace(/\D/g, '').slice(0, 16)
         number.value = digits.replace(/(.{4})/g, '$1 ').trim()
      })

      expiry.addEventListener('input', () => {
         const digits = expiry.value.replace(/\D/g, '').slice(0, 4)
         expiry.value = digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits
      })

      cvc.addEventListener('input', () => {
         cvc.value = cvc.value.replace(/\D/g, '').slice(0, 4)
      })

      cardForm.addEventListener('submit', event => {
         event.preventDefault()
         let valid = true
         const digits = number.value.replace(/\D/g, '')

         if (digits.length !== 16) {
            markError(number, 'Enter the 16 digits on your card.')
            valid = false
         }

         const match = expiry.value.match(/^(\d{2})\/(\d{2})$/)
         if (!match || Number(match[1]) < 1 || Number(match[1]) > 12) {
            markError(expiry, 'Use MM/YY.')
            valid = false
         }

         if (cvc.value.length < 3) {
            markError(cvc, '3–4 digits.')
            valid = false
         }

         if (!valid) {
            showToast('Check your card details.', 'error')
            return
         }

         const last4 = digits.slice(-4)
         $$('[data-card-last4]').forEach(el => { el.textContent = last4 })
         $$('[data-card-exp]').forEach(el => { el.textContent = expiry.value })
         $$('[data-card-number]').forEach(el => { el.textContent = `•••• •••• •••• ${last4}` })

         closeModal($('#card-modal'))
         showToast(`Card ending ${last4} saved.`)
         cardForm.reset()
      })
   }

   $$('[data-invoice]').forEach(button => {
      button.addEventListener('click', () => showToast(`Invoice ${button.dataset.invoice} downloaded.`))
   })

   $$('[data-toast]').forEach(button => {
      button.addEventListener('click', () => showToast(button.dataset.toast))
   })

   $$('[data-scroll]').forEach(link => {
      link.addEventListener('click', event => {
         const target = document.querySelector(link.dataset.scroll)
         if (!target) return
         event.preventDefault()
         target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
      })
   })
}

/*=============== CREATE WIZARD ===============*/
const wizard = $('#wizard')

if (wizard) {
   const SPEAKERS = {
      Maya: { name: 'Maya Chen', role: 'Host', cls: 'c-mint', voice: 'Nova', sample: 'The sign says closed, but the door is still open.' },
      Dev: { name: 'Dev Patel', role: 'Guest', cls: 'c-clay', voice: 'Atlas', sample: 'Everything in this shop has a story, even the dust.' },
      Iris: { name: 'Iris Bell', role: 'Expert', cls: 'c-lilac', voice: 'Juno', sample: 'The future of listening is smaller, stranger and far more personal.' },
      Narrator: { name: 'Narrator', role: 'Narration', cls: 'c-blue', voice: 'Sage', sample: 'Recorded live, on the last night the needle ever dropped.' }
   }

   const VOICES = {
      Nova: { sample: 'Hi, I’m Nova. Warm, patient and built for long-form stories.', pitch: 1.05, rate: 0.94 },
      Atlas: { sample: 'Atlas here. Big ideas sound better with a little gravel underneath.', pitch: 0.85, rate: 0.96 },
      Juno: { sample: 'Juno speaking. Clear, curious and always leaning forward.', pitch: 1.1, rate: 1.02 },
      Milo: { sample: 'Hey, Milo. Quick takes, bright edges, zero filler.', pitch: 1.15, rate: 1.08 },
      Sage: { sample: 'Sage. Measured, cinematic and impossible to rush.', pitch: 0.92, rate: 0.9 },
      Pixel: { sample: 'Pixel online. Playful, synthetic and a little unpredictable.', pitch: 1.25, rate: 1.05 }
   }

   const clonedVoice = name => getClonedVoices().find(voice => voice.name === name) || null

   const voiceMeta = name => {
      if (VOICES[name]) return VOICES[name]
      const cloned = clonedVoice(name)
      return cloned
         ? { sample: `This is ${cloned.name}. Your own voice, ready to cast.`, pitch: 1, rate: 1, cloned: true, id: cloned.id }
         : VOICES.Nova
   }

   const voiceGroups = () => {
      const stock = Object.keys(VOICES)
      const taken = stock.map(name => name.toLowerCase())
      const cloned = getClonedVoices()
         .filter(voice => !taken.includes(voice.name.toLowerCase()))
         .map(voice => voice.name)
      return { stock, cloned }
   }

   const GENRES = {
      narrative: { label: 'Narrative', palette: 'c-sun', variant: 'rings' },
      interview: { label: 'Interview', palette: 'c-mint', variant: 'wave' },
      comedy: { label: 'Comedy', palette: 'c-clay', variant: 'disc' },
      documentary: { label: 'Documentary', palette: 'c-blue', variant: 'grid' },
      scifi: { label: 'Sci-Fi', palette: 'c-lilac', variant: 'rings' },
      education: { label: 'Education', palette: 'c-moss', variant: 'type' }
   }

   const MUSIC = {
      none: 'No music bed',
      warm: 'Warm strings',
      cinematic: 'Cinematic drift',
      lofi: 'Lo-fi keys',
      tension: 'Low tension'
   }

   const FORMATS = {
      mp3: 'MP3 · 320 kbps',
      wav: 'WAV · 48 kHz'
   }

   const EMOTIONS = ['Neutral', 'Warm', 'Excited', 'Somber', 'Urgent']
   const PACES = ['Slow', 'Steady', 'Quick']
   const PITCHES = ['Low', 'Mid', 'High']
   const PACE_RATE = { Slow: 0.8, Steady: 1, Quick: 1.25 }
   const PACE_PITCH = { Low: 0.85, Mid: 1, High: 1.15 }

   let lineCounter = 0
   const nextId = () => `ln-${Date.now().toString(36)}-${++lineCounter}`

   const makeLine = (speaker = 'Maya', text = '') => ({
      id: nextId(),
      speaker,
      text,
      style: { emotion: 'Warm', pace: 'Steady', pitch: 'Mid' }
   })

   const defaultState = () => ({
      step: 1,
      title: '',
      scene: '',
      scenario: '',
      genre: 'narrative',
      language: 'English (US)',
      lines: [makeLine('Maya'), makeLine('Dev')],
      cast: { Maya: 'Nova', Dev: 'Atlas', Iris: 'Juno', Narrator: 'Sage' },
      music: 'warm',
      format: 'mp3',
      rights: false,
      updated: null
   })

   let state = defaultState()

   const scriptLines = $('#script-lines')
   const summaryCover = $('#summary-cover')
   const saveStatus = $('#save-status')

   const fields = {
      title: $('#pod-title'),
      scene: $('#pod-scene'),
      scenario: $('#pod-scenario'),
      genre: $('#pod-genre'),
      language: $('#pod-language'),
      music: $('#music-bed')
   }

   const speakerOrder = ['Maya', 'Dev', 'Iris', 'Narrator']

   const genreMeta = () => GENRES[state.genre] || GENRES.narrative
   const lineWordCount = text => text.trim() ? text.trim().split(/\s+/).length : 0
   const totalWords = () => state.lines.reduce((total, line) => total + lineWordCount(line.text), 0)
   const filledLines = () => state.lines.filter(line => line.text.trim())
   const usedSpeakers = () => {
      const names = [...new Set(state.lines.map(line => line.speaker))]
      return names.length ? names : ['Maya']
   }

   const runtimeSeconds = () => {
      let seconds = 0
      filledLines().forEach(line => {
         const rate = PACE_RATE[line.style.pace] || 1
         seconds += (lineWordCount(line.text) / (150 * rate)) * 60 + 1.2
      })
      return Math.max(filledLines().length ? 8 : 0, Math.round(seconds))
   }

   const setSaveStatus = (text, done = true) => {
      if (!saveStatus) return
      saveStatus.innerHTML = `<i class="${done ? 'ri-cloud-line' : 'ri-loader-4-line'}" aria-hidden="true"></i><span>${text}</span>`
   }

   let draftCleared = false

   const hasDraftContent = () => Boolean(
      state.title.trim() ||
      state.scene.trim() ||
      state.scenario.trim() ||
      state.lines.some(line => line.text.trim())
   )

   const saveDraft = (announce = false) => {
      if (draftCleared) return

      if (!hasDraftContent()) {
         clearDraft()
         setSaveStatus('Autosaves as you type')
         if (announce) showToast('Add a title or a line before saving.', 'error')
         return
      }

      state.updated = Date.now()
      const ok = store.set(DRAFT_KEY, state)
      setSaveStatus(ok ? 'Saved to this browser' : 'Could not save draft')
      if (announce) showToast(ok ? 'Draft saved to this browser.' : 'Draft could not be saved.', ok ? 'ok' : 'error')
   }

   const queueSave = debounce(() => saveDraft(false), 500)

   const touchDraft = () => {
      draftCleared = false
      setSaveStatus('Saving…', false)
      queueSave()
   }

   const clearDraft = () => store.remove(DRAFT_KEY)

   const syncFormFields = () => {
      fields.title.value = state.title
      fields.scene.value = state.scene
      fields.scenario.value = state.scenario
      fields.genre.value = state.genre
      fields.language.value = state.language
      fields.music.value = state.music
      $$('input[name="format"]').forEach(input => { input.checked = input.value === state.format })
      const rights = $('#rights')
      if (rights) rights.checked = state.rights
   }

   const resizeTextarea = textarea => {
      textarea.style.height = 'auto'
      textarea.style.height = `${textarea.scrollHeight}px`
   }

   const renderSummary = () => {
      const meta = genreMeta()
      const title = state.title.trim() || 'Untitled podcast'
      const letter = title.replace(/[^a-z0-9]/gi, '').charAt(0) || 'V'

      if (summaryCover) {
         renderCover(summaryCover, {
            variant: meta.variant,
            palette: meta.palette,
            letter,
            tag: meta.label
         })
      }

      const titleEl = $('#summary-title')
      if (titleEl) titleEl.textContent = title
      const metaEl = $('#summary-meta')
      if (metaEl) metaEl.textContent = `${meta.label} · ${state.language}`

      const lineCount = filledLines().length
      const castCount = new Set(filledLines().map(line => line.speaker)).size
      const seconds = runtimeSeconds()

      if ($('#summary-lines')) $('#summary-lines').textContent = `${lineCount} ${lineCount === 1 ? 'line' : 'lines'}`
      if ($('#summary-cast')) $('#summary-cast').textContent = castCount ? `${castCount} ${castCount === 1 ? 'voice' : 'voices'}` : '—'
      if ($('#summary-runtime')) $('#summary-runtime').textContent = seconds ? formatClock(seconds) : '—'
      if ($('#summary-format')) $('#summary-format').textContent = FORMATS[state.format]

      const progress = [
         Boolean(state.title.trim() && state.scene.trim() && state.scenario.trim()),
         lineCount > 0,
         lineCount > 0 && usedSpeakers().every(speaker => state.cast[speaker]),
         Boolean(state.rights)
      ]

      $$('[data-summary-step]').forEach((item, index) => {
         const icon = item.querySelector('i')
         if (!icon) return
         const done = progress[index]
         icon.className = done ? 'ri-checkbox-circle-fill' : 'ri-circle-line'
         item.classList.toggle('is-done', done)
      })
   }

   const styleLabel = line => `${line.style.emotion} · ${line.style.pace} · ${line.style.pitch} pitch`

   const updateLineChrome = lineElement => {
      const line = state.lines.find(item => item.id === lineElement.dataset.lineId)
      if (!line) return
      const words = lineWordCount(line.text)
      const count = lineElement.querySelector('.line__count')
      if (count) count.textContent = `${words} ${words === 1 ? 'word' : 'words'}`
      const chipText = lineElement.querySelector('[data-style-label]')
      if (chipText) chipText.textContent = styleLabel(line)
      const play = lineElement.querySelector('[data-line-play]')
      if (play) play.dataset.text = line.text
   }

   const updateScriptMeta = () => {
      const lineCount = filledLines().length
      const words = totalWords()
      const seconds = runtimeSeconds()

      if ($('#script-meta-lines')) $('#script-meta-lines').textContent = `${lineCount} ${lineCount === 1 ? 'line' : 'lines'}`
      if ($('#script-meta-words')) $('#script-meta-words').textContent = `${words} ${words === 1 ? 'word' : 'words'}`
      if ($('#script-meta-runtime')) $('#script-meta-runtime').textContent = seconds ? `~${formatClock(seconds)} runtime` : 'No runtime yet'

      const empty = $('#script-empty')
      if (empty) empty.classList.toggle('is-visible', state.lines.length === 0)
   }

   const buildSegRow = (line, group, label, values) => {
      const row = document.createElement('div')
      row.className = 'style-row'

      const rowLabel = document.createElement('span')
      rowLabel.className = 'style-row__label'
      rowLabel.textContent = label

      const seg = document.createElement('div')
      seg.className = 'seg'
      seg.setAttribute('role', 'radiogroup')
      seg.setAttribute('aria-label', label)

      values.forEach(value => {
         const wrapper = document.createElement('label')
         const input = document.createElement('input')
         input.type = 'radio'
         input.name = `${group}-${line.id}`
         input.value = value
         input.checked = line.style[group] === value
         input.dataset.styleGroup = group

         const text = document.createElement('span')
         text.textContent = value

         wrapper.append(input, text)
         seg.appendChild(wrapper)
      })

      row.append(rowLabel, seg)
      return row
   }

   const buildLine = (line, index, total) => {
      const speaker = SPEAKERS[line.speaker] || SPEAKERS.Maya
      const element = document.createElement('div')
      element.className = 'line'
      element.dataset.lineId = line.id

      const avatar = document.createElement('span')
      avatar.className = `line__avatar avatar ${speaker.cls}`
      avatar.setAttribute('aria-hidden', 'true')
      avatar.textContent = initialsOf(speaker.name)

      const main = document.createElement('div')
      main.className = 'line__main'

      const top = document.createElement('div')
      top.className = 'line__top'

      const who = document.createElement('div')
      who.className = 'line__who'

      const select = document.createElement('select')
      select.className = 'line__select'
      select.dataset.lineSpeaker = ''
      select.setAttribute('aria-label', `Speaker for line ${index + 1}`)
      Object.entries(SPEAKERS).forEach(([key, value]) => {
         const option = document.createElement('option')
         option.value = key
         option.textContent = value.name
         option.selected = key === line.speaker
         select.appendChild(option)
      })

      const chevron = document.createElement('i')
      chevron.className = 'ri-arrow-down-s-line'
      chevron.setAttribute('aria-hidden', 'true')

      const role = document.createElement('span')
      role.className = 'line__role'
      role.textContent = speaker.role

      who.append(select, chevron, role)

      const tools = document.createElement('div')
      tools.className = 'line__tools'

      const makeTool = (label, icon, action, danger = false) => {
         const button = document.createElement('button')
         button.type = 'button'
         button.className = `icon-btn${danger ? ' is-danger' : ''}`
         button.setAttribute('aria-label', label)
         button.dataset[action] = ''
         button.disabled = (action === 'lineUp' && index === 0) || (action === 'lineDown' && index === total - 1)
         button.innerHTML = `<i class="${icon}" aria-hidden="true"></i>`
         return button
      }

      tools.append(
         makeTool('Move line up', 'ri-arrow-up-line', 'lineUp'),
         makeTool('Move line down', 'ri-arrow-down-line', 'lineDown'),
         makeTool('Delete line', 'ri-delete-bin-line', 'lineDelete', true)
      )

      top.append(who, tools)

      const textarea = document.createElement('textarea')
      textarea.className = 'line__text'
      textarea.rows = 1
      textarea.placeholder = `What does ${firstNameOf(speaker.name)} say?`
      textarea.value = line.text
      textarea.dataset.lineText = ''
      textarea.setAttribute('aria-label', `Dialogue for ${speaker.name}, line ${index + 1}`)

      const foot = document.createElement('div')
      foot.className = 'line__foot'

      const styleButton = document.createElement('button')
      styleButton.type = 'button'
      styleButton.className = 'style-chip'
      styleButton.dataset.styleToggle = ''
      styleButton.setAttribute('aria-expanded', 'false')
      styleButton.innerHTML = '<i class="ri-equalizer-2-line" aria-hidden="true"></i><span data-style-label></span><i class="ri-arrow-down-s-line" aria-hidden="true"></i>'
      styleButton.querySelector('[data-style-label]').textContent = styleLabel(line)

      const footRight = document.createElement('span')
      footRight.className = 'line__foot-actions'

      const play = document.createElement('button')
      play.type = 'button'
      play.className = 'icon-btn js-speak'
      play.dataset.text = line.text
      play.dataset.pitch = String((PACE_PITCH[line.style.pitch] || 1) * voiceMeta(state.cast[line.speaker]).pitch)
      play.dataset.rate = String(PACE_RATE[line.style.pace] || 1)
      play.setAttribute('aria-label', `Preview ${speaker.name}'s line`)
      play.innerHTML = '<i class="ri-play-circle-line" aria-hidden="true"></i>'
      play.dataset.linePlay = ''

      const count = document.createElement('span')
      count.className = 'line__count'
      count.textContent = `${lineWordCount(line.text)} words`

      footRight.append(play, count)
      foot.append(styleButton, footRight)

      const panel = document.createElement('div')
      panel.className = 'style-panel'
      panel.hidden = true
      panel.append(
         buildSegRow(line, 'emotion', 'Emotion', EMOTIONS),
         buildSegRow(line, 'pace', 'Pace', PACES),
         buildSegRow(line, 'pitch', 'Pitch', PITCHES)
      )

      main.append(top, textarea, foot, panel)
      element.append(avatar, main)
      return element
   }

   const renderLines = focusId => {
      if (!scriptLines) return
      scriptLines.replaceChildren()

      state.lines.forEach((line, index) => {
         scriptLines.appendChild(buildLine(line, index, state.lines.length))
      })

      $$('.line__text', scriptLines).forEach(resizeTextarea)

      if (focusId) {
         const target = scriptLines.querySelector(`[data-line-id="${focusId}"] .line__text`)
         if (target) {
            target.focus()
            target.setSelectionRange(target.value.length, target.value.length)
         }
      }

      updateScriptMeta()
      renderSummary()
   }

   const renderCast = () => {
      const list = $('#cast-list')
      if (!list) return
      list.replaceChildren()

      usedSpeakers().forEach(speakerKey => {
         const speaker = SPEAKERS[speakerKey] || SPEAKERS.Maya
         const voice = state.cast[speakerKey] || speaker.voice
         const data = voiceMeta(voice)

         const card = document.createElement('div')
         card.className = 'cast-card'

         const avatar = document.createElement('span')
         avatar.className = `avatar ${speaker.cls}`
         avatar.setAttribute('aria-hidden', 'true')
         avatar.textContent = initialsOf(speaker.name)

         const info = document.createElement('div')
         const name = document.createElement('div')
         name.className = 'cast-card__name'
         name.textContent = speaker.name
         const role = document.createElement('div')
         role.className = 'cast-card__role'
         role.textContent = speaker.role
         info.append(name, role)

         const controls = document.createElement('div')
         controls.className = 'cast-card__controls'

         const selectWrap = document.createElement('div')
         selectWrap.className = 'select-wrap'
         const select = document.createElement('select')
         select.className = 'select'
         select.dataset.castSpeaker = speakerKey
         select.setAttribute('aria-label', `Voice for ${speaker.name}`)
         const addGroup = (label, names) => {
            if (!names.length) return
            const group = document.createElement('optgroup')
            group.label = label
            names.forEach(voiceName => {
               const option = document.createElement('option')
               option.value = voiceName
               option.textContent = voiceName
               option.selected = voiceName === voice
               group.appendChild(option)
            })
            select.appendChild(group)
         }

         const groups = voiceGroups()
         addGroup('My cloned voices', groups.cloned)
         addGroup('Voxa voices', groups.stock)

         const chevron = document.createElement('i')
         chevron.className = 'ri-arrow-down-s-line'
         chevron.setAttribute('aria-hidden', 'true')
         selectWrap.append(select, chevron)

         const play = document.createElement('button')
         play.type = 'button'
         play.className = 'play-btn'
         play.setAttribute('aria-label', data.cloned && clonedSample(clonedVoice(voice))
            ? `Play the ${voice} sample`
            : `Preview ${voice}`)
         play.innerHTML = '<i class="ri-play-fill" aria-hidden="true"></i>'

         if (data.cloned && clonedSample(clonedVoice(voice))) {
            play.dataset.voicePlay = data.id
         } else {
            play.classList.add('js-speak')
            play.dataset.text = data.sample
            play.dataset.pitch = String(data.pitch)
            play.dataset.rate = String(data.rate)
         }

         if (data.cloned) {
            const badge = document.createElement('span')
            badge.className = 'chip chip--clone'
            badge.textContent = 'Cloned'
            name.append(badge)
         }

         controls.append(selectWrap, play)
         card.append(avatar, info, controls)
         list.appendChild(card)
      })
   }

   const renderReview = () => {
      const meta = genreMeta()
      const seconds = runtimeSeconds()
      const castNames = usedSpeakers().map(key => SPEAKERS[key]?.name || key)

      const set = (selector, value) => {
         const el = $(selector)
         if (el) el.textContent = value
      }

      set('#review-title', state.title.trim() || 'Untitled podcast')
      set('#review-scene', state.scene.trim() || 'No scene description yet.')
      set('#review-scenario', state.scenario.trim() || 'No scenario description yet.')
      set('#review-genre', meta.label)
      set('#review-language', state.language)
      set('#review-lines', `${filledLines().length}`)
      set('#review-cast', `${castNames.length}`)
      set('#review-runtime', seconds ? formatClock(seconds) : '—')
      set('#review-music', MUSIC[state.music] || 'No music bed')
      set('#review-format', FORMATS[state.format])

      const preview = $('#review-script')
      if (preview) {
         preview.replaceChildren()
         filledLines().forEach(line => {
            const speaker = SPEAKERS[line.speaker] || SPEAKERS.Maya
            const row = document.createElement('div')
            row.className = 'preview-line'
            const name = document.createElement('strong')
            name.textContent = speaker.name
            const note = document.createElement('em')
            note.textContent = `${line.style.emotion} · ${line.style.pace}`
            name.appendChild(note)
            const text = document.createElement('p')
            text.textContent = line.text
            row.append(name, text)
            preview.appendChild(row)
         })

         if (!filledLines().length) {
            const note = document.createElement('p')
            note.textContent = 'No dialogue yet — go back to step 2 to add lines.'
            preview.appendChild(note)
         }
      }
   }

   const setStep = (step, scroll = true) => {
      state.step = step

      $$('[data-step-pane]').forEach(pane => {
         pane.classList.toggle('is-active', Number(pane.dataset.stepPane) === step)
      })

      $$('.wstep').forEach(button => {
         const value = Number(button.dataset.step)
         button.classList.toggle('is-active', value === step)
         button.classList.toggle('is-done', value < step)
         button.setAttribute('aria-current', value === step ? 'step' : 'false')
         const num = button.querySelector('.wstep__num')
         if (num) num.innerHTML = value < step ? '<i class="ri-check-line" aria-hidden="true"></i>' : String(value)
      })

      if (step === 2) renderLines()
      if (step === 3) renderCast()
      if (step === 4) renderReview()
      renderSummary()

      if (scroll) {
         wizard.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
      }
   }

   const setFieldError = (input, message) => {
      const field = input.closest('.field')
      if (!field) return
      field.classList.add('is-error')
      const error = field.querySelector('.field__error')
      if (error) error.textContent = message
   }

   const clearFieldError = input => input.closest('.field')?.classList.remove('is-error')

   const validateStep = step => {
      if (step === 1) {
         let firstInvalid = null

         if (state.title.trim().length < 3) {
            setFieldError(fields.title, 'Give your episode a title (3+ characters).')
            firstInvalid = firstInvalid || fields.title
         } else {
            clearFieldError(fields.title)
         }

         if (state.scene.trim().length < 15) {
            setFieldError(fields.scene, 'Set the scene in at least 15 characters.')
            firstInvalid = firstInvalid || fields.scene
         } else {
            clearFieldError(fields.scene)
         }

         if (state.scenario.trim().length < 30) {
            setFieldError(fields.scenario, 'Describe what happens in at least 30 characters.')
            firstInvalid = firstInvalid || fields.scenario
         } else {
            clearFieldError(fields.scenario)
         }

         if (firstInvalid) {
            firstInvalid.focus()
            showToast('Add the story details before moving on.', 'error')
            return false
         }
      }

      if (step === 2) {
         if (!filledLines().length) {
            showToast('Write at least one line of dialogue.', 'error')
            const target = $('.line__text', scriptLines)
            if (target) target.focus()
            return false
         }

         const tooShort = state.lines.find(line => line.text.trim() && line.text.trim().length < 3)
         if (tooShort) {
            showToast('Each spoken line needs at least 3 characters.', 'error')
            return false
         }
      }

      if (step === 4 && !state.rights) {
         showToast('Confirm you have the rights to publish this episode.', 'error')
         const rights = $('#rights')
         if (rights) rights.focus()
         return false
      }

      return true
   }

   const goToStep = target => {
      if (target === state.step) return

      if (target > state.step) {
         for (let step = state.step; step < target; step++) {
            if (!validateStep(step)) {
               if (step !== state.step) setStep(step)
               return
            }
         }
      }

      setStep(target)
   }

   /*---------- Dialogue events ----------*/
   if (scriptLines) {
      scriptLines.addEventListener('click', event => {
         const lineElement = event.target.closest('.line')
         if (!lineElement) return
         const index = state.lines.findIndex(line => line.id === lineElement.dataset.lineId)
         if (index < 0) return

         if (event.target.closest('[data-style-toggle]')) {
            const panel = lineElement.querySelector('.style-panel')
            const toggle = event.target.closest('[data-style-toggle]')
            const open = panel.hidden
            panel.hidden = !open
            toggle.setAttribute('aria-expanded', String(open))
            if (open) {
               lineElement.querySelector('.style-panel input:checked')?.focus()
            }
            return
         }

         if (event.target.closest('[data-line-up]')) {
            if (index === 0) return
            ;[state.lines[index - 1], state.lines[index]] = [state.lines[index], state.lines[index - 1]]
            renderLines()
            touchDraft()
            return
         }

         if (event.target.closest('[data-line-down]')) {
            if (index === state.lines.length - 1) return
            ;[state.lines[index + 1], state.lines[index]] = [state.lines[index], state.lines[index + 1]]
            renderLines()
            touchDraft()
            return
         }

         if (event.target.closest('[data-line-delete]')) {
            state.lines.splice(index, 1)
            renderLines()
            touchDraft()
            renderSummary()
            return
         }
      })

      scriptLines.addEventListener('change', event => {
         const lineElement = event.target.closest('.line')
         if (!lineElement) return
         const line = state.lines.find(item => item.id === lineElement.dataset.lineId)
         if (!line) return

         if (event.target.matches('[data-line-speaker]')) {
            line.speaker = event.target.value
            renderLines()
            touchDraft()
            renderSummary()
            return
         }

         if (event.target.matches('[data-style-group]')) {
            line.style[event.target.dataset.styleGroup] = event.target.value
            updateLineChrome(lineElement)
            const play = lineElement.querySelector('[data-line-play]')
            if (play) {
               play.dataset.pitch = String((PACE_PITCH[line.style.pitch] || 1) * voiceMeta(state.cast[line.speaker]).pitch)
               play.dataset.rate = String(PACE_RATE[line.style.pace] || 1)
            }
            touchDraft()
            renderSummary()
         }
      })

      scriptLines.addEventListener('input', event => {
         const textarea = event.target.closest('.line__text')
         if (!textarea) return
         const lineElement = textarea.closest('.line')
         const line = state.lines.find(item => item.id === lineElement.dataset.lineId)
         if (!line) return

         line.text = textarea.value
         resizeTextarea(textarea)
         updateLineChrome(lineElement)
         updateScriptMeta()
         renderSummary()
         touchDraft()
      })

      scriptLines.addEventListener('focusin', event => {
         const textarea = event.target.closest('.line__text')
         if (textarea) textarea.closest('.line').classList.add('is-focus')
      })

      scriptLines.addEventListener('focusout', event => {
         const textarea = event.target.closest('.line__text')
         if (textarea) textarea.closest('.line').classList.remove('is-focus')
      })
   }

   const addLine = (speaker, focus = true) => {
      const key = speaker || speakerOrder[state.lines.length % speakerOrder.length]
      const line = makeLine(key)
      state.lines.push(line)
      renderLines(focus ? line.id : null)
      const target = scriptLines?.querySelector(`[data-line-id="${line.id}"]`)
      target?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
      updateScriptMeta()
      renderSummary()
      touchDraft()
   }

   $('#add-line')?.addEventListener('click', () => addLine())
   $('#empty-add')?.addEventListener('click', () => addLine('Maya'))

   /*---------- Step 1 fields ----------*/
   fields.title.addEventListener('input', () => {
      state.title = fields.title.value
      clearFieldError(fields.title)
      renderSummary()
      touchDraft()
   })

   fields.scene.addEventListener('input', () => {
      state.scene = fields.scene.value
      clearFieldError(fields.scene)
      touchDraft()
   })

   fields.scenario.addEventListener('input', () => {
      state.scenario = fields.scenario.value
      clearFieldError(fields.scenario)
      renderSummary()
      touchDraft()
   })

   fields.genre.addEventListener('change', () => {
      state.genre = fields.genre.value
      renderSummary()
      touchDraft()
   })

   fields.language.addEventListener('change', () => {
      state.language = fields.language.value
      renderSummary()
      touchDraft()
   })

   fields.music.addEventListener('change', () => {
      state.music = fields.music.value
      renderSummary()
      touchDraft()
   })

   $$('input[name="format"]').forEach(input => {
      input.addEventListener('change', () => {
         if (!input.checked) return
         state.format = input.value
         renderSummary()
         touchDraft()
      })
   })

   const rights = $('#rights')
   if (rights) {
      rights.addEventListener('change', () => {
         state.rights = rights.checked
         renderSummary()
         touchDraft()
      })
   }

   /*---------- Cast events ----------*/
   const castList = $('#cast-list')
   if (castList) {
      castList.addEventListener('change', event => {
         const select = event.target.closest('[data-cast-speaker]')
         if (!select) return
         state.cast[select.dataset.castSpeaker] = select.value
         renderCast()
         renderSummary()
         touchDraft()
      })
   }

   /*---------- Steps / navigation ----------*/
   $$('.wstep').forEach(button => {
      button.addEventListener('click', () => goToStep(Number(button.dataset.step)))
   })

   $$('[data-next]').forEach(button => {
      button.addEventListener('click', () => goToStep(state.step + 1))
   })

   $$('[data-back]').forEach(button => {
      button.addEventListener('click', () => goToStep(Math.max(1, state.step - 1)))
   })

   $('#save-draft')?.addEventListener('click', () => saveDraft(true))

   /*---------- Example / restore ----------*/
   const loadExample = (remix = false) => {
      state = {
         ...defaultState(),
         title: remix ? 'The Last Record Shop — Remix' : 'The Last Record Shop',
         scene: 'A rain-soaked evening in a narrow Tokyo side street, 1998. Neon hums above a shop that has sold vinyl for forty years.',
         scenario: 'Maya visits Mr. Sato’s closing record shop to record one final interview before the shutters come down. Their conversation drifts from vinyl crackle to the future of listening, and what we lose when a place like this disappears.',
         genre: 'narrative',
         language: 'English (US)',
         lines: [
            { ...makeLine('Maya', 'The sign says closed, but the door is still open. Mind if I come in?'), style: { emotion: 'Warm', pace: 'Steady', pitch: 'Mid' } },
            { ...makeLine('Dev', 'Only if you don’t mind the smell of old cardboard and better music.'), style: { emotion: 'Warm', pace: 'Slow', pitch: 'Low' } },
            { ...makeLine('Maya', 'That’s exactly the smell I flew nine thousand miles for.'), style: { emotion: 'Excited', pace: 'Quick', pitch: 'High' } },
            { ...makeLine('Dev', 'Then pull up a crate. Everything in this shop has a story, even the dust.'), style: { emotion: 'Warm', pace: 'Steady', pitch: 'Low' } },
            { ...makeLine('Maya', 'Tell me the story of the dust, then.'), style: { emotion: 'Neutral', pace: 'Slow', pitch: 'Mid' } },
            { ...makeLine('Dev', 'It’s the same story as mine. It settled here, and it never wanted to leave.'), style: { emotion: 'Somber', pace: 'Slow', pitch: 'Low' } },
            { ...makeLine('Narrator', 'Recorded live at Sato Records, on the last night the needle ever dropped.'), style: { emotion: 'Neutral', pace: 'Slow', pitch: 'Mid' } }
         ],
         music: 'lofi',
         format: 'mp3',
         rights: false
      }
      lineCounter = 0
      draftCleared = false
      syncFormFields()
      setStep(1, false)
      renderLines()
      renderCast()
      renderSummary()
      saveDraft(false)
      showToast(remix ? 'Remix template loaded.' : 'Example loaded. Tweak it or generate as is.')
   }

   $('#load-example')?.addEventListener('click', () => loadExample(false))

   const params = new URLSearchParams(window.location.search)
   const saved = store.get(DRAFT_KEY)
   const savedHasContent = saved && Array.isArray(saved.lines) && Boolean(
      (saved.title || '').trim() ||
      (saved.scene || '').trim() ||
      (saved.scenario || '').trim() ||
      saved.lines.some(line => (line.text || '').trim())
   )

   if (savedHasContent) {
      state = {
         ...defaultState(),
         ...saved,
         step: 1,
         cast: { ...defaultState().cast, ...(saved.cast || {}) }
      }

      const available = new Set([...voiceGroups().stock, ...voiceGroups().cloned])
      Object.keys(state.cast).forEach(key => {
         if (!available.has(state.cast[key])) state.cast[key] = SPEAKERS[key]?.voice || 'Nova'
      })

      syncFormFields()
      setStep(1, false)
      renderLines()
      setSaveStatus('Draft restored')
   } else {
      if (saved) clearDraft()
      syncFormFields()
      setStep(1, false)
      renderLines()
      setSaveStatus('Autosaves as you type')
   }

   if (params.has('remix')) loadExample(true)

   /*---------- Generate episode ----------*/
   const renderModal = $('#render-modal')
   const renderLoading = $('#render-loading')
   const renderSuccess = $('#render-success')
   const renderBar = $('#render-bar')
   const stageNodes = $$('[data-render-stage]')

   let rendering = false

   const buildEpisode = () => {
      const meta = genreMeta()
      const title = state.title.trim() || 'Untitled podcast'
      const seconds = runtimeSeconds()
      const castNames = usedSpeakers().map(key => SPEAKERS[key]?.name || key)
      const script = filledLines()
         .map(line => `${SPEAKERS[line.speaker]?.name || line.speaker}: ${line.text.trim()}`)
         .join(' ')

      return {
         id: `ep-${Date.now()}`,
         title,
         genre: state.genre,
         genreLabel: meta.label,
         author: getUser().name,
         duration: formatClock(seconds),
         seconds,
         lines: filledLines().length,
         cast: castNames,
         voices: usedSpeakers().map(key => state.cast[key] || SPEAKERS[key]?.voice).filter(Boolean),
         plays: 0,
         createdAt: new Date().toISOString(),
         script,
         spec: {
            variant: meta.variant,
            palette: meta.palette,
            letter: title.replace(/[^a-z0-9]/gi, '').charAt(0) || 'V'
         }
      }
   }

   const finishRender = episode => {
      const coverHost = $('#render-success-cover')
      if (coverHost) {
         const tag = 'Ready'
         renderCover(coverHost, { ...episode.spec, tag })
      }

      const title = $('#render-success-title')
      if (title) title.textContent = episode.title
      const meta = $('#render-success-meta')
      if (meta) meta.textContent = `${episode.genreLabel} · ${episode.duration} · ${episode.cast.length} voices`

      const listen = $('#listen-render')
      if (listen) listen.dataset.text = episode.script

      addUserEpisode(episode)
      draftCleared = true
      clearDraft()
      setSaveStatus('Draft cleared after render')

      renderLoading?.classList.add('is-hidden')
      renderSuccess?.classList.add('is-active')
      rendering = false
   }

   const runRender = episode => {
      rendering = true

      $$('.render-stage').forEach(stage => {
         stage.classList.remove('is-active', 'is-done')
         const icon = stage.querySelector('i')
         if (icon) icon.className = 'ri-loader-4-line'
      })

      if (renderBar) renderBar.style.width = '8%'

      stageNodes.forEach((stage, index) => {
         setTimeout(() => {
            stageNodes.forEach((item, itemIndex) => {
               if (itemIndex < index) {
                  item.classList.remove('is-active')
                  item.classList.add('is-done')
                  const icon = item.querySelector('i')
                  if (icon) icon.className = 'ri-checkbox-circle-fill'
               }
            })
            stage.classList.add('is-active')
            if (renderBar) renderBar.style.width = `${18 + (index / stageNodes.length) * 70}%`
         }, index * 780)
      })

      setTimeout(() => {
         if (renderBar) renderBar.style.width = '100%'
         stageNodes.forEach(stage => {
            stage.classList.remove('is-active')
            stage.classList.add('is-done')
            const icon = stage.querySelector('i')
            if (icon) icon.className = 'ri-checkbox-circle-fill'
         })
         setTimeout(() => finishRender(episode), 420)
      }, stageNodes.length * 780 + 300)
   }

   const resetRenderModal = () => {
      renderLoading?.classList.remove('is-hidden')
      renderSuccess?.classList.remove('is-active')
      if (renderBar) renderBar.style.width = '0%'
      $$('.render-stage').forEach(stage => {
         stage.classList.remove('is-active', 'is-done')
         const icon = stage.querySelector('i')
         if (icon) icon.className = 'ri-loader-4-line'
      })
   }

   $('#generate-btn')?.addEventListener('click', () => {
      for (let step = 1; step <= 4; step++) {
         if (!validateStep(step)) {
            if (step < 4) setStep(step)
            return
         }
      }

      if (rendering) return

      const episode = buildEpisode()
      window.__voxaLastRender = episode

      resetRenderModal()
      openModal('render-modal')
      runRender(episode)
   })

   $('#render-again')?.addEventListener('click', () => {
      closeModal(renderModal)
      state = defaultState()
      syncFormFields()
      setSaveStatus('Autosaves as you type')
      draftCleared = true
      clearDraft()
      setStep(1, false)
      renderLines()
      renderSummary()
   })

   /*---------- Keyboard: keep wizard drafts on unload ----------*/
   window.addEventListener('beforeunload', () => {
      if (!rendering) saveDraft(false)
   })
}
