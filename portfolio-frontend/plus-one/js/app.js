/*=============== APP PAGES · shared behaviour ===============*/
(() => {
   'use strict'

   const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
   const $ = (selector, root = document) => root.querySelector(selector)
   const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector))
   const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms))

   const esc = value => String(value).replace(/[&<>"']/g, ch => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
   })[ch])

   const store = {
      get(key, fallback = null) {
         try {
            const raw = window.localStorage.getItem(key)
            return raw ? JSON.parse(raw) : fallback
         } catch {
            return fallback
         }
      },
      set(key, value) {
         try {
            window.localStorage.setItem(key, JSON.stringify(value))
            return true
         } catch {
            return false
         }
      },
      remove(key) {
         try {
            window.localStorage.removeItem(key)
         } catch {
            /* ignore */
         }
      }
   }

   const getSession = () => store.get('plusone:session')
   const setSession = session => store.set('plusone:session', session)
   const clearSession = () => store.remove('plusone:session')

   const initials = name => String(name || 'Plus One')
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map(part => part.charAt(0))
      .join('')
      .toUpperCase() || 'PO'

   const firstName = name => String(name || '').trim().split(/\s+/)[0] || 'there'

   const nameFromEmail = email => String(email || '')
      .split('@')[0]
      .replace(/[._-]+/g, ' ')
      .trim()
      .split(/\s+/)
      .map(part => part ? part.charAt(0).toUpperCase() + part.slice(1) : '')
      .join(' ') || 'Plus One'

   const money = amount => {
      const rounded = Math.round(amount * 100) / 100
      return rounded % 1 === 0 ? `$${rounded}` : `$${rounded.toFixed(2)}`
   }

   const formatDate = value => new Date(value).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
   })

   const slugify = value => String(value || 'plus-one')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48) || 'plus-one'

   const validEmail = value => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(String(value).trim())

   /*=============== HEADER ===============*/
   const header = $('#header')
   const nav = $('.nav')
   const navMenu = $('#nav-menu')
   const navToggle = $('#nav-toggle')
   const navClose = $('#nav-close')

   if (navToggle && navMenu && nav) {
      const openMenu = () => {
         navMenu.classList.add('show-menu')
         nav.classList.add('is-open')
         navToggle.setAttribute('aria-expanded', 'true')
         document.body.style.overflow = 'hidden'
      }

      const closeMenu = () => {
         navMenu.classList.remove('show-menu')
         nav.classList.remove('is-open')
         navToggle.setAttribute('aria-expanded', 'false')
         document.body.style.overflow = ''
      }

      navToggle.addEventListener('click', openMenu)
      navClose.addEventListener('click', closeMenu)
      $$('.nav__link, .nav__cta').forEach(link => link.addEventListener('click', closeMenu))
      document.addEventListener('keydown', event => {
         if (event.key === 'Escape' && navMenu.classList.contains('show-menu')) closeMenu()
      })
   }

   if (header) {
      const scrollHeader = () => header.classList.toggle('scroll-header', window.scrollY >= 40)
      window.addEventListener('scroll', scrollHeader, { passive: true })
      scrollHeader()
   }

   /*=============== TOAST ===============*/
   const toastEl = $('#toast')
   let toastTimer

   const showToast = (message, duration = 2600) => {
      if (!toastEl) return
      toastEl.textContent = message
      toastEl.classList.add('is-on')
      window.clearTimeout(toastTimer)
      toastTimer = window.setTimeout(() => toastEl.classList.remove('is-on'), duration)
   }

   /*=============== ACCOUNT CHIP ===============*/
   const paintAccount = () => {
      const session = getSession()
      $$('[data-account]').forEach(node => {
         if (session) {
            node.href = 'dashboard.html'
            node.classList.add('nav__cta--user')
            node.innerHTML = `<span class="nav__initials">${esc(initials(session.name))}</span><span>${esc(firstName(session.name))}</span>`
            node.setAttribute('aria-label', `${session.name} — open your dashboard`)
         } else {
            node.href = 'auth.html'
            node.classList.remove('nav__cta--user')
            node.textContent = 'Log in'
            node.setAttribute('aria-label', 'Log in or create an account')
         }
      })
   }

   paintAccount()

   /*=============== AUTH PAGE ===============*/
   const initAuth = () => {
      const sessionBanner = $('#auth-session')
      const tabs = { login: $('#tab-login'), register: $('#tab-register') }
      const forms = { login: $('#login-form'), register: $('#register-form') }
      const resetPanel = $('#reset-panel')
      const title = $('#auth-title')
      const subtitle = $('#auth-sub')
      const switchBox = $('#auth-switch')
      let mode = 'login'

      const paintSession = () => {
         const current = getSession()
         if (!sessionBanner) return
         sessionBanner.hidden = !current
         if (current) {
            $('#auth-session-name').textContent = current.name || current.email
            const email = $('#login-email')
            if (email && !email.value) email.value = current.email || ''
         }
      }

      const renderSwitch = () => {
         if (!switchBox) return
         switchBox.innerHTML = mode === 'login'
            ? 'New here? <button type="button" data-switch="register">Create an account</button>'
            : 'Already with us? <button type="button" data-switch="login">Log in instead</button>'
         switchBox.querySelector('button').addEventListener('click', () => {
            if (mode === 'login') showRegister()
            else showLogin()
         })
      }

      const showPanel = panel => {
         if (!tabs.login) return
         mode = panel
         Object.entries(tabs).forEach(([key, tab]) => {
            const active = key === panel
            tab.setAttribute('aria-selected', String(active))
            tab.tabIndex = active ? 0 : -1
         })
         if (forms.login) forms.login.hidden = panel !== 'login'
         if (forms.register) forms.register.hidden = panel !== 'register'
         if (resetPanel) resetPanel.hidden = true
         renderSwitch()
      }

      const showLogin = (updateHash = true) => {
         showPanel('login')
         title.textContent = 'Welcome back.'
         subtitle.textContent = 'Your camera has been waiting.'
         if (updateHash) history.replaceState(null, '', '#login')
      }

      const showRegister = (updateHash = true) => {
         showPanel('register')
         title.textContent = 'Start your first roll.'
         subtitle.textContent = 'One event free. No card needed.'
         if (updateHash) history.replaceState(null, '', '#register')
      }

      const showReset = () => {
         if (forms.login) forms.login.hidden = true
         if (forms.register) forms.register.hidden = true
         if (resetPanel) resetPanel.hidden = false
         title.textContent = 'Reset your password.'
         subtitle.textContent = 'We will email you a fresh way in.'
         const email = $('#login-email')
         const resetEmail = $('#reset-email')
         if (resetEmail && email && email.value) resetEmail.value = email.value
         if (resetEmail) resetEmail.focus()
         if (switchBox) switchBox.hidden = true
      }

      const backToLogin = () => {
         if (switchBox) switchBox.hidden = false
         showLogin()
      }

      if (window.location.hash === '#register') showRegister(false)
      else if (window.location.hash === '#login') showLogin(false)
      else showLogin(false)

      paintSession()

      if (tabs.login) {
         tabs.login.addEventListener('click', () => showLogin())
         tabs.register.addEventListener('click', () => showRegister())
      }

      window.addEventListener('hashchange', () => {
         if (window.location.hash === '#register') showRegister(false)
         else if (window.location.hash === '#login') showLogin(false)
      })

      $('.auth__tabs')?.addEventListener('keydown', event => {
         if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
         event.preventDefault()
         if (mode === 'login') showRegister()
         else showLogin()
         tabs[mode].focus()
      })

      $('#auth-forget')?.addEventListener('click', () => {
         clearSession()
         paintSession()
         paintAccount()
         showToast('Signed out on this device.')
      })

      $$('[data-eye]').forEach(button => {
         button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.eye)
            if (!input) return
            const reveal = input.type === 'password'
            input.type = reveal ? 'text' : 'password'
            button.querySelector('i').className = reveal ? 'ri-eye-off-line' : 'ri-eye-line'
            button.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password')
         })
      })

      const setFieldError = (input, message) => {
         if (!input) return
         const field = input.closest('.auth__field')
         const error = field?.querySelector('.auth__error')
         if (field) field.classList.toggle('is-invalid', Boolean(message))
         input.setAttribute('aria-invalid', String(Boolean(message)))
         if (error) {
            error.textContent = message
            error.hidden = !message
         }
      }

      /* --- log in --- */
      const loginForm = $('#login-form')
      if (loginForm) {
         const email = $('#login-email')
         const password = $('#login-password')
         const button = $('button[type="submit"]', loginForm)

         email.addEventListener('input', () => setFieldError(email, ''))
         password.addEventListener('input', () => setFieldError(password, ''))

         loginForm.addEventListener('submit', async event => {
            event.preventDefault()
            const invalid = []
            if (!validEmail(email.value)) {
               setFieldError(email, 'Enter the email you signed up with.')
               invalid.push(email)
            } else setFieldError(email, '')
            if (password.value.length < 6) {
               setFieldError(password, 'Passwords are at least 6 characters.')
               invalid.push(password)
            } else setFieldError(password, '')

            if (invalid.length) {
               invalid[0].focus()
               return
            }

            button.disabled = true
            button.classList.add('is-loading')
            button.innerHTML = '<span>Signing in</span><i class="ri-loader-4-line"></i>'
            await sleep(800)

            const existing = getSession()
            const emailValue = email.value.trim()
            setSession({
               name: existing?.name || nameFromEmail(emailValue),
               email: emailValue,
               plan: existing?.plan || 'plusone',
               since: existing?.since || new Date().toISOString()
            })
            paintAccount()

            button.classList.remove('is-loading')
            button.innerHTML = '<span>Signed in</span><i class="ri-check-line"></i>'
            showToast('Signed in — opening your dashboard.')
            await sleep(500)
            window.location.href = 'dashboard.html'
         })
      }

      /* --- register --- */
      const registerForm = $('#register-form')
      if (registerForm) {
         const name = $('#reg-name')
         const email = $('#reg-email')
         const password = $('#reg-password')
         const terms = $('#reg-terms')
         const termsError = $('#reg-terms-error')
         const strength = $('#reg-strength')
         const strengthLabel = $('#reg-strength-label')
         const button = $('button[type="submit"]', registerForm)

         const scorePassword = value => {
            if (!value) return 0
            let score = 0
            if (value.length >= 8) score += 1
            if (value.length >= 12 || (/[a-z]/.test(value) && /[A-Z]/.test(value))) score += 1
            if (/\d/.test(value)) score += 1
            if (/[^A-Za-z0-9]/.test(value)) score += 1
            return Math.max(1, Math.min(4, score))
         }

         const strengthText = ['At least 8 characters', 'Weak — add length', 'Fair — add a number', 'Good — nearly there', 'Strong — hard to guess']

         password.addEventListener('input', () => {
            const score = scorePassword(password.value)
            strength.dataset.score = String(score)
            strengthLabel.textContent = strengthText[score]
            if (password.value.length >= 8) setFieldError(password, '')
         })

         name.addEventListener('input', () => setFieldError(name, ''))
         email.addEventListener('input', () => setFieldError(email, ''))
         if (terms) {
            terms.addEventListener('change', () => {
               if (termsError) termsError.hidden = terms.checked
            })
         }

         registerForm.addEventListener('submit', async event => {
            event.preventDefault()
            const invalid = []
            if (name.value.trim().length < 2) {
               setFieldError(name, 'Tell us what to call you.')
               invalid.push(name)
            } else setFieldError(name, '')
            if (!validEmail(email.value)) {
               setFieldError(email, 'That email does not look right.')
               invalid.push(email)
            } else setFieldError(email, '')
            if (password.value.length < 8) {
               setFieldError(password, 'Use at least 8 characters.')
               invalid.push(password)
            } else setFieldError(password, '')
            if (terms && !terms.checked) {
               if (termsError) termsError.hidden = false
               if (!invalid.length) terms.focus()
            } else if (termsError) {
               termsError.hidden = true
            }

            if (invalid.length) {
               invalid[0].focus()
               return
            }

            button.disabled = true
            button.classList.add('is-loading')
            button.innerHTML = '<span>Creating account</span><i class="ri-loader-4-line"></i>'
            await sleep(950)

            const emailValue = email.value.trim()
            setSession({
               name: name.value.trim(),
               email: emailValue,
               plan: 'guest',
               since: new Date().toISOString()
            })
            paintAccount()

            button.classList.remove('is-loading')
            button.innerHTML = '<span>Account created</span><i class="ri-check-line"></i>'
            showToast('Welcome in — one event is on us.')
            await sleep(550)
            window.location.href = 'dashboard.html'
         })
      }

      /* --- reset --- */
      $('#forgot-btn')?.addEventListener('click', showReset)
      $('#reset-back')?.addEventListener('click', backToLogin)

      const resetForm = $('#reset-form')
      if (resetForm) {
         const email = $('#reset-email')
         const button = $('button[type="submit"]', resetForm)
         email.addEventListener('input', () => setFieldError(email, ''))
         resetForm.addEventListener('submit', async event => {
            event.preventDefault()
            if (!validEmail(email.value)) {
               setFieldError(email, 'Enter the email on your account.')
               email.focus()
               return
            }
            setFieldError(email, '')
            button.disabled = true
            button.classList.add('is-loading')
            button.innerHTML = '<span>Sending link</span><i class="ri-loader-4-line"></i>'
            await sleep(900)
            button.classList.remove('is-loading')
            button.disabled = false
            button.innerHTML = '<span>Send reset link</span><i class="ri-arrow-right-line"></i>'
            showToast(`Reset link sent to ${email.value.trim()}.`, 3600)
            backToLogin()
         })
      }

      /* --- social --- */
      $$('#auth-social button').forEach(button => {
         button.addEventListener('click', async () => {
            const provider = button.dataset.social
            const icon = button.querySelector('i')
            button.disabled = true
            icon.className = 'ri-loader-4-line'
            await sleep(700)

            const email = provider === 'apple' ? 'nia.okafor@icloud.com' : 'nia.okafor@gmail.com'
            setSession({
               name: 'Nia Okafor',
               email,
               plan: 'plusone',
               since: new Date().toISOString()
            })
            paintAccount()
            showToast(`Signed in with ${provider === 'apple' ? 'Apple' : 'Google'}.`)
            await sleep(450)
            window.location.href = 'dashboard.html'
         })
      })
   }

   /*=============== PRICING PAGE ===============*/
   const initPricing = () => {
      const PLANS = {
         plusone: {
            name: 'Plus One',
            monthly: 14,
            annual: 140,
            sub: 'Unlimited events · up to 8 people',
            features: ['Unlimited events', 'Up to 8 people', '300 frames per event', 'Full-resolution downloads', 'Private albums, retrain any time']
         },
         whole: {
            name: 'The Whole Table',
            monthly: 29,
            annual: 290,
            sub: 'The family archive · up to 25 people',
            features: ['Everything in Plus One', 'Up to 25 people', '1,000 frames per event', 'Print-ready files', 'Two seats, one shared album']
         }
      }

      const params = new URLSearchParams(window.location.search)
      const requested = params.get('plan')
      const session = getSession()

      const state = {
         plan: requested && PLANS[requested] ? requested : (session?.plan && PLANS[session.plan] ? session.plan : 'plusone'),
         cycle: 'monthly',
         promo: null
      }

      const cycleButtons = $$('[data-cycle]')
      const planCards = $$('.plan [data-choose]')
      const payForm = $('#pay-form')
      const cardInput = $('#pay-card')
      const brandEl = $('#card-brand')
      const expiryInput = $('#pay-expiry')
      const cvcInput = $('#pay-cvc')
      const promoForm = $('#promo-form')
      const promoInput = $('#promo-code')
      const promoNote = $('#promo-note')
      const payButton = $('#pay-submit')
      const orderTitle = $('#order-title')
      const orderSub = $('#order-sub')
      const orderPlan = $('#order-plan')
      const orderCycle = $('#order-cycle')
      const orderTotal = $('#order-total')
      const orderFeatures = $('#order-features')
      const discountRow = $('#order-discount-row')
      const discountValue = $('#order-discount')
      const checkoutGrid = $('#checkout-grid')
      const receipt = $('#receipt')

      const planPrice = key => PLANS[key][state.cycle]

      const totals = () => {
         const base = planPrice(state.plan)
         const discount = state.promo ? Math.round(base * 0.2 * 100) / 100 : 0
         return { base, discount, total: Math.round((base - discount) * 100) / 100 }
      }

      const cycleText = () => state.cycle === 'monthly' ? 'Monthly' : 'Annual · 2 months free'

      const renderSummary = () => {
         const plan = PLANS[state.plan]
         const { discount, total } = totals()

         if (orderTitle) orderTitle.textContent = plan.name
         if (orderSub) orderSub.textContent = plan.sub
         if (orderPlan) orderPlan.textContent = plan.name
         if (orderCycle) orderCycle.textContent = cycleText()
         if (orderTotal) orderTotal.textContent = money(total)
         if (discountRow) discountRow.hidden = !state.promo
         if (discountValue) discountValue.textContent = `−${money(discount)}`
         if (orderFeatures) {
            orderFeatures.innerHTML = plan.features.map(feature => `<li>${esc(feature)}</li>`).join('')
         }
         if (payButton) {
            payButton.innerHTML = `<span>Pay ${money(total)} today</span><i class="ri-arrow-right-line"></i>`
         }
         if (promoNote && !promoNote.dataset.override) {
            promoNote.className = 'promo__note'
            promoNote.textContent = state.promo
               ? `${state.promo} applied — 20% off your first payment. Clear the field and apply to remove.`
               : 'Have an invite? Try FIRSTROLL for 20% off.'
         }
      }

      const renderPrices = () => {
         $$('[data-price-for]').forEach(node => {
            const key = node.dataset.priceFor
            const plan = PLANS[key]
            if (!plan) return
            const amount = node.querySelector('[data-amount]')
            const cadence = node.querySelector('[data-cycle-label]')
            if (amount) amount.textContent = money(plan[state.cycle])
            if (cadence) cadence.textContent = state.cycle === 'monthly' ? '/month' : '/year'
         })
         $$('[data-billing]').forEach(node => {
            node.textContent = state.cycle === 'monthly' ? 'Billed monthly' : 'Billed yearly · 2 months free'
         })
      }

      const renderSelection = () => {
         planCards.forEach(card => {
            const key = card.dataset.choose
            const active = key === state.plan
            const plan = PLANS[key]
            const cardEl = card.closest('.plan')
            if (cardEl) cardEl.classList.toggle('is-selected', active)
            card.setAttribute('aria-pressed', String(active))
            card.textContent = active ? 'Selected' : `Choose ${plan.name}`
         })
         renderSummary()
      }

      const setCycle = cycle => {
         state.cycle = cycle === 'annual' ? 'annual' : 'monthly'
         cycleButtons.forEach(button => {
            const active = button.dataset.cycle === state.cycle
            button.classList.toggle('is-active', active)
            button.setAttribute('aria-pressed', String(active))
         })
         renderPrices()
         renderSummary()
      }

      const selectPlan = (key, options = {}) => {
         if (!PLANS[key]) return
         state.plan = key
         renderSelection()
         if (options.updateUrl !== false) {
            const url = new URL(window.location.href)
            url.searchParams.set('plan', key)
            history.replaceState(null, '', `${url.pathname.split('/').pop()}${url.search}${url.hash}`)
         }
         if (options.scroll) {
            $('#checkout')?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
         }
      }

      cycleButtons.forEach(button => {
         button.addEventListener('click', () => setCycle(button.dataset.cycle))
      })

      planCards.forEach(card => {
         card.addEventListener('click', () => selectPlan(card.dataset.choose, { scroll: true }))
      })

      setCycle('monthly')
      selectPlan(state.plan, { updateUrl: false })

      if (session?.email) {
         const email = $('#pay-email')
         const name = $('#pay-name')
         if (email) email.value = session.email
         if (name && session.name) name.value = session.name
      }

      /* --- card formatting --- */
      const brandOf = digits => {
         if (!digits) return 'Card'
         if (/^4/.test(digits)) return 'Visa'
         if (/^(5[1-5]|2[2-7])/.test(digits)) return 'Mastercard'
         if (/^3[47]/.test(digits)) return 'Amex'
         if (/^6/.test(digits)) return 'Discover'
         return 'Card'
      }

      if (cardInput) {
         cardInput.addEventListener('input', () => {
            const digits = cardInput.value.replace(/\D/g, '').slice(0, 19)
            cardInput.value = digits.replace(/(.{4})/g, '$1 ').trim()
            if (brandEl) brandEl.textContent = brandOf(digits)
            if (cardInput.closest('.formfield')?.classList.contains('is-invalid')) setPayError(cardInput, '')
         })
      }

      if (expiryInput) {
         expiryInput.addEventListener('input', () => {
            const digits = expiryInput.value.replace(/\D/g, '').slice(0, 4)
            expiryInput.value = digits.length > 2 ? `${digits.slice(0, 2)} / ${digits.slice(2)}` : digits
            if (expiryInput.closest('.formfield')?.classList.contains('is-invalid')) setPayError(expiryInput, '')
         })
      }

      if (cvcInput) {
         cvcInput.addEventListener('input', () => {
            cvcInput.value = cvcInput.value.replace(/\D/g, '').slice(0, 4)
            if (cvcInput.closest('.formfield')?.classList.contains('is-invalid')) setPayError(cvcInput, '')
         })
      }

      $$('#pay-form input').forEach(input => {
         input.addEventListener('input', () => {
            if (input.closest('.formfield')?.classList.contains('is-invalid')) setPayError(input, '')
         })
      })

      /* --- validation --- */
      const setPayError = (input, message) => {
         const field = input.closest('.formfield')
         const error = field?.querySelector('.formfield__error')
         if (field) field.classList.toggle('is-invalid', Boolean(message))
         input.setAttribute('aria-invalid', String(Boolean(message)))
         if (error) {
            error.textContent = message
            error.hidden = !message
         }
      }

      const luhn = value => {
         let sum = 0
         let double = false
         for (let index = value.length - 1; index >= 0; index -= 1) {
            let digit = Number(value[index])
            if (double) {
               digit *= 2
               if (digit > 9) digit -= 9
            }
            sum += digit
            double = !double
         }
         return sum % 10 === 0
      }

      const expiryIsFuture = value => {
         const match = value.match(/^(\d{2})\s*\/\s*(\d{2})$/)
         if (!match) return false
         const month = Number(match[1])
         const year = 2000 + Number(match[2])
         if (month < 1 || month > 12) return false
         const now = new Date()
         return new Date(year, month, 1) > new Date(now.getFullYear(), now.getMonth(), 1)
      }

      const validatePay = () => {
         const email = $('#pay-email')
         const name = $('#pay-name')
         const zip = $('#pay-zip')
         const invalid = []

         if (!validEmail(email.value)) {
            setPayError(email, 'Enter a valid email for the receipt.')
            invalid.push(email)
         }
         if (name.value.trim().length < 2) {
            setPayError(name, 'Add the name printed on the card.')
            invalid.push(name)
         }
         const digits = cardInput.value.replace(/\D/g, '')
         if (digits.length < 13 || digits.length > 19 || !luhn(digits)) {
            setPayError(cardInput, 'Check the card number.')
            invalid.push(cardInput)
         }
         if (!expiryIsFuture(expiryInput.value.trim())) {
            setPayError(expiryInput, 'Use a future MM / YY date.')
            invalid.push(expiryInput)
         }
         if (!/^\d{3,4}$/.test(cvcInput.value)) {
            setPayError(cvcInput, '3 or 4 digits.')
            invalid.push(cvcInput)
         }
         if (!/^[A-Za-z0-9 -]{3,10}$/.test(zip.value.trim())) {
            setPayError(zip, 'Add a billing postcode.')
            invalid.push(zip)
         }

         if (invalid.length) {
            invalid[0].focus()
            invalid[0].closest('.formfield')?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
            return false
         }
         return true
      }

      /* --- promo --- */
      const applyPromo = () => {
         const code = promoInput.value.trim().toUpperCase()
         promoNote.dataset.override = ''

         if (!code) {
            state.promo = null
            renderSummary()
            return
         }

         if (code === 'FIRSTROLL') {
            state.promo = 'FIRSTROLL'
            renderSummary()
            showToast('Invite code applied — 20% off.')
         } else {
            state.promo = null
            renderSummary()
            promoNote.className = 'promo__note is-bad'
            promoNote.textContent = 'That invite code is not valid. Try FIRSTROLL.'
            promoNote.dataset.override = '1'
            showToast('That invite code is not valid.')
         }
      }

      promoForm?.addEventListener('submit', event => {
         event.preventDefault()
         applyPromo()
      })

      /* --- receipt --- */
      const downloadReceipt = () => {
         const details = window.__receipt
         if (!details) return
         const lines = [
            'PLUS ONE — PAYMENT RECEIPT',
            '==========================',
            '',
            `Invoice     ${details.invoice}`,
            `Date        ${details.dateLabel}`,
            `Plan        ${details.plan} (${details.cycle})`,
            `Amount      ${details.amount}`,
            `Card        ${details.card}`,
            `Billed to   ${details.email}`,
            '',
            details.promo ? `Invite code ${details.promo} — 20% off applied` : 'No invite code applied',
            '',
            'Demo checkout — no card was charged.',
            'Thank you for keeping the camera.'
         ]
         const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
         const url = URL.createObjectURL(blob)
         const link = document.createElement('a')
         link.href = url
         link.download = `plus-one-receipt-${details.invoice}.txt`
         document.body.append(link)
         link.click()
         link.remove()
         window.setTimeout(() => URL.revokeObjectURL(url), 4000)
         showToast('Receipt downloaded.')
      }

      const completePurchase = () => {
         const plan = PLANS[state.plan]
         const { total } = totals()
         const digits = cardInput.value.replace(/\D/g, '')
         const last4 = digits.slice(-4)
         const brand = brandOf(digits)
         const now = new Date()
         const invoice = `PO-${now.getFullYear()}-${Math.random().toString(16).slice(2, 6).toUpperCase()}`
         const name = $('#pay-name').value.trim()
         const email = $('#pay-email').value.trim()
         const cycleLabel = state.cycle === 'monthly' ? 'Monthly' : 'Annual'

         setSession({
            name: session?.name || name,
            email: session?.email || email,
            plan: state.plan,
            since: session?.since || now.toISOString(),
            billing: {
               cycle: state.cycle,
               amount: total,
               invoice,
               date: now.toISOString(),
               last4,
               brand
            }
         })
         paintAccount()

         window.__receipt = {
            invoice,
            dateLabel: formatDate(now),
            plan: plan.name,
            cycle: cycleLabel,
            amount: money(total),
            card: `${brand} •••• ${last4}`,
            email,
            promo: state.promo
         }

         $('#receipt-title').textContent = `You're in, ${firstName(name)}.`
         $('#receipt-lede').textContent = `${plan.name} is active. Your camera is ready for the next Saturday.`
         $('#receipt-invoice').textContent = invoice
         $('#receipt-plan').textContent = `${plan.name} · ${cycleLabel}`
         $('#receipt-amount').textContent = state.promo ? `${money(total)} · 20% off` : money(total)
         $('#receipt-card').textContent = `${brand} •••• ${last4}`
         $('#receipt-email').textContent = email

         if (checkoutGrid) checkoutGrid.hidden = true
         if (receipt) receipt.hidden = false
         $('#receipt-title').focus({ preventScroll: true })
         receipt?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
         showToast(`${plan.name} is active. Welcome in.`, 3600)
      }

      payForm?.addEventListener('submit', async event => {
         event.preventDefault()
         if (!validatePay()) return

         payButton.disabled = true
         payButton.classList.add('is-loading')
         payButton.innerHTML = '<span>Processing payment</span><i class="ri-loader-4-line"></i>'
         await sleep(1500)
         completePurchase()
      })

      $('#receipt-download')?.addEventListener('click', downloadReceipt)
   }

   /*=============== DASHBOARD PAGE ===============*/
   const initDashboard = () => {
      const OCCASIONS = {
         wedding: 'Wedding',
         roadtrip: 'Road trip',
         graduation: 'Graduation',
         picnic: 'Picnic'
      }

      const DEMO_ALBUMS = [
         {
            id: 'demo-wedding',
            title: "Priya & Tom's wedding",
            venue: 'Golden Hour Farm, Hudson Valley',
            occasion: 'wedding',
            occasionLabel: 'Wedding',
            activities: ['Ceremony', 'Confetti', 'The first dance', 'The toast'],
            frames: 148,
            people: 9,
            cover: 'img/event-wedding.jpg',
            date: '14 Jun 2026',
            sample: true
         },
         {
            id: 'demo-roadtrip',
            title: 'Route 12, the long way',
            venue: 'Escalante, UT',
            occasion: 'roadtrip',
            occasionLabel: 'Road trip',
            activities: ['Gas stop', 'Road snacks', 'The lookout'],
            frames: 63,
            people: 7,
            cover: 'img/event-roadtrip.jpg',
            date: '02 May 2026',
            sample: true
         },
         {
            id: 'demo-graduation',
            title: "Maya's graduation",
            venue: 'Chapel Hill, NC',
            occasion: 'graduation',
            occasionLabel: 'Graduation',
            activities: ['The walk across', 'Cap toss', 'Family photos'],
            frames: 96,
            people: 6,
            cover: 'img/event-graduation.jpg',
            date: '17 May 2026',
            sample: true
         },
         {
            id: 'demo-picnic',
            title: 'Sunday, no plans',
            venue: 'Prospect Park, Brooklyn',
            occasion: 'picnic',
            occasionLabel: 'Picnic',
            activities: ['The blanket', 'Lemonade', 'Frisbee', 'Golden hour'],
            frames: 74,
            people: 11,
            cover: 'img/event-picnic.jpg',
            date: '28 Sep 2026',
            sample: true
         }
      ]

      const CAST = [
         { name: 'Nia Okafor', role: 'You · admin', events: 4, image: 'img/seed-1.jpg' },
         { name: 'Kai Mensah', role: 'Partner', events: 3, image: 'img/seed-2.jpg' },
         { name: 'Priya Shah', role: 'Bride', events: 2, image: 'img/seed-3.jpg' },
         { name: 'Tom Reyes', role: 'Groom', events: 2, image: 'img/seed-4.jpg' },
         { name: 'Ruth Okafor', role: 'Grandma', events: 5, image: 'img/pic-lemonade.jpg' },
         { name: 'Maya Okafor', role: 'Sister', events: 3, image: 'img/grad-family.jpg' }
      ]

      const SAVED = [
         { src: 'img/wed-confetti.jpg', title: 'Catching confetti', meta: 'Golden Hour Farm · 4:52 pm', filter: 'brightness(1.02) contrast(1.02) saturate(1.08) sepia(0.14) hue-rotate(-4deg)', zoom: 1.08, pos: '50% 40%' },
         { src: 'img/event-picnic.jpg', title: 'The whole blanket', meta: 'Prospect Park · 3:05 pm', filter: 'grayscale(1) contrast(1.08) brightness(1.02)', zoom: 1.12, pos: '50% 55%' },
         { src: 'img/rt-window.jpg', title: 'Hair out the window', meta: 'Route 12 · 7:12 pm', filter: 'brightness(0.96) contrast(1.03) saturate(0.94) hue-rotate(8deg)', zoom: 1.05, pos: '50% 45%' },
         { src: 'img/grad-cap.jpg', title: 'Caps in the air', meta: 'Chapel Hill · 2:11 pm', filter: 'brightness(1.03) contrast(1.06) saturate(1.1)', zoom: 1, pos: '50% 50%' },
         { src: 'img/pic-frisbee.jpg', title: 'Nearly took out the stroller', meta: 'Prospect Park · 3:40 pm', filter: 'brightness(1.04) contrast(1.02) saturate(1.05)', zoom: 1.15, pos: '50% 35%' },
         { src: 'img/wed-toast.jpg', title: 'Grandpa’s speech, still going', meta: 'Golden Hour Farm · 8:58 pm', filter: 'brightness(1.01) contrast(0.98) saturate(0.95) sepia(0.16) hue-rotate(-3deg)', zoom: 1.06, pos: '50% 45%' },
         { src: 'img/grad-family.jpg', title: 'The hug after', meta: 'Chapel Hill · 1:20 pm', filter: 'brightness(1.04) contrast(0.94) saturate(0.9) sepia(0.1)', zoom: 1.04, pos: '50% 38%' },
         { src: 'img/pic-lemonade.jpg', title: 'Lemonade going warm', meta: 'Prospect Park · 2:30 pm', filter: 'brightness(1.06) contrast(1.02) saturate(1.04) sepia(0.12)', zoom: 1.1, pos: '50% 40%' }
      ]

      const PLAN_META = {
         guest: {
            name: 'Guest',
            price: '$0',
            cadence: 'one event',
            cap: 20,
            features: ['1 event album', 'Up to 3 people', '20 frames', '720px exports'],
            cta: 'Choose a plan'
         },
         plusone: {
            name: 'Plus One',
            price: '$14',
            cadence: '/ month',
            cap: 300,
            features: ['Unlimited events', 'Up to 8 people', '300 frames per event', 'Full-resolution downloads', 'Private albums, retrain any time'],
            cta: 'Manage membership'
         },
         whole: {
            name: 'The Whole Table',
            price: '$29',
            cadence: '/ month',
            cap: 1000,
            features: ['Everything in Plus One', 'Up to 25 people', '1,000 frames per event', 'Print-ready files', 'Two seats, one shared album'],
            cta: 'Manage membership'
         }
      }

      const session = getSession()
      const storedAlbums = (store.get('plusone:albums', []) || [])
         .filter(album => album && album.title)
         .map(album => ({
            ...album,
            occasion: OCCASIONS[album.occasion] ? album.occasion : 'wedding',
            occasionLabel: album.occasionLabel || OCCASIONS[album.occasion] || 'Album',
            activities: Array.isArray(album.activities) ? album.activities : [],
            frames: Number(album.frames) || 0,
            people: Number(album.people) || 4,
            cover: album.cover || 'img/event-wedding.jpg',
            date: album.createdAt ? formatDate(album.createdAt) : '',
            sample: false
         }))

      const albums = [...storedAlbums, ...DEMO_ALBUMS]
      const people = CAST.map(person => ({ ...person, fresh: false }))
      const state = {
         view: 'overview',
         filter: 'all',
         search: '',
         peopleSearch: ''
      }

      const name = session?.name || 'Nia Okafor'
      const email = session?.email || 'nia@plusone.studio'
      const planKey = session?.plan && PLAN_META[session.plan] ? session.plan : 'plusone'
      const plan = PLAN_META[planKey]

      /* --- account paint --- */
      const setText = (selector, value) => {
         const node = $(selector)
         if (node) node.textContent = value
      }

      setText('#side-name', name)
      setText('#side-email', email)
      setText('#side-avatar', initials(name))
      setText('#top-avatar', initials(name))
      setText('#dash-date', new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }))

      const hour = new Date().getHours()
      const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
      const greetingEl = $('#greeting')
      if (greetingEl) greetingEl.innerHTML = `${greeting}, <em>${esc(firstName(name))}.</em>`

      /* --- stats --- */
      const totalFrames = albums.reduce((sum, album) => sum + album.frames, 0)

      setText('#stat-albums', String(albums.length))
      setText('#stat-frames', totalFrames.toLocaleString('en-US'))
      setText('#stat-people', String(people.length))
      setText('#stat-saved', String(SAVED.length))
      setText('#albums-meta', `${albums.length} rolls · ${totalFrames.toLocaleString('en-US')} frames`)
      setText('#people-meta', `${people.length} faces · all consented`)
      setText('#wall-count-label', `${SAVED.length} frames saved`)

      /* --- plan --- */
      const cap = plan.cap
      const storedFrames = storedAlbums.reduce((sum, album) => sum + album.frames, 0)
      const baseUsed = planKey === 'whole' ? 412 : planKey === 'guest' ? 6 : 212
      const used = Math.min(cap, baseUsed + storedFrames)
      const usage = Math.round((used / cap) * 100)
      const nextRenewal = new Date()
      nextRenewal.setMonth(nextRenewal.getMonth() + 1)

      const planMeta = planKey === 'guest'
         ? 'One event · no renewal'
         : `${used} of ${cap.toLocaleString('en-US')} frames · renews ${formatDate(nextRenewal)}`

      setText('#side-plan-name', plan.name)
      setText('#side-plan-price', `${plan.price} ${plan.cadence}`)
      setText('#side-plan-meta', planMeta)
      setText('#box-plan-name', plan.name)
      setText('#box-plan-meta', planMeta)
      setText('#box-plan-status', planKey === 'guest' ? 'Free' : 'Active')
      setText('#box-plan-cta', plan.cta)

      const priceNode = $('#box-plan-price')
      if (priceNode) priceNode.innerHTML = `<b>${esc(plan.price)}</b> ${esc(plan.cadence)}`

      const listNode = $('#box-plan-list')
      if (listNode) listNode.innerHTML = plan.features.map(feature => `<li>${esc(feature)}</li>`).join('')

      const fillBar = node => {
         if (node) node.style.width = `${Math.min(100, usage)}%`
      }
      window.requestAnimationFrame(() => {
         fillBar($('#side-plan-bar'))
         fillBar($('#box-plan-bar'))
      })

      /* --- album cards --- */
      const albumFilters = $$('[data-filter]')
      const albumGrid = $('#album-grid')
      const albumsEmpty = $('#albums-empty')
      const albumSearch = $('#album-search')

      const albumHref = album => {
         const params = new URLSearchParams({
            occasion: album.occasion,
            title: album.title,
            venue: album.venue
         })
         if (album.activities.length) params.set('activities', album.activities.join(','))
         return `studio.html?${params.toString()}#brief`
      }

      const albumCard = album => `
         <article class="albumcard" data-occasion="${esc(album.occasion)}" data-search="${esc(`${album.title} ${album.venue}`.toLowerCase())}">
            <a class="albumcard__media" href="${esc(albumHref(album))}" aria-label="Start a roll like ${esc(album.title)}">
               <img src="${esc(album.cover)}" alt="${esc(album.title)}" loading="lazy">
               ${album.sample ? '<span class="albumcard__badge">Sample roll</span>' : ''}
               <span class="albumcard__frames">${album.frames} frames</span>
            </a>
            <div class="albumcard__body">
               <h3>${esc(album.title)}</h3>
               <p class="albumcard__meta"><i class="ri-map-pin-2-line"></i>${esc(album.venue)}${album.date ? ` · ${esc(album.date)}` : ''}</p>
               <ul class="albumcard__tags">
                  ${album.activities.slice(0, 3).map(activity => `<li>${esc(activity)}</li>`).join('')}
               </ul>
               <div class="albumcard__foot">
                  <span class="albumcard__people">${album.people} people</span>
                  <a class="albumcard__open" href="${esc(albumHref(album))}">Open <i class="ri-arrow-right-up-line"></i></a>
               </div>
            </div>
         </article>`

      const renderAlbums = () => {
         if (!albumGrid) return
         const query = state.search.trim().toLowerCase()
         const visible = albums.filter(album => {
            const matchesFilter = state.filter === 'all' || album.occasion === state.filter
            const matchesQuery = !query || `${album.title} ${album.venue}`.toLowerCase().includes(query)
            return matchesFilter && matchesQuery
         })

         albumGrid.innerHTML = visible.map(albumCard).join('')
         if (albumsEmpty) albumsEmpty.hidden = visible.length > 0

         albumFilters.forEach(button => {
            const filter = button.dataset.filter
            const count = filter === 'all' ? albums.length : albums.filter(album => album.occasion === filter).length
            const badge = button.querySelector('span')
            if (badge) badge.textContent = String(count)
         })
      }

      const renderRecent = () => {
         const recent = $('#recent-albums')
         if (!recent) return
         recent.innerHTML = albums.slice(0, 3).map(album => `
            <a class="recent__card" href="${esc(albumHref(album))}">
               <span class="recent__cover">
                  <img src="${esc(album.cover)}" alt="${esc(album.title)}" loading="lazy">
                  <span class="recent__count">${album.frames}</span>
               </span>
               <span class="recent__title">${esc(album.title)}</span>
               <span class="recent__meta">${esc(album.venue)} · ${esc(album.occasionLabel)}</span>
            </a>`).join('')
      }

      albumFilters.forEach(button => {
         button.addEventListener('click', () => {
            state.filter = button.dataset.filter
            albumFilters.forEach(item => item.setAttribute('aria-pressed', String(item === button)))
            renderAlbums()
         })
      })

      albumSearch?.addEventListener('input', () => {
         state.search = albumSearch.value
         renderAlbums()
      })

      /* --- activity --- */
      const timeAgo = value => {
         const diff = Math.max(0, Date.now() - new Date(value).getTime())
         const minutes = Math.round(diff / 60000)
         if (minutes < 1) return 'just now'
         if (minutes < 60) return `${minutes} min ago`
         const hours = Math.round(minutes / 60)
         if (hours < 24) return `${hours} hr${hours === 1 ? '' : 's'} ago`
         const days = Math.round(hours / 24)
         return `${days} day${days === 1 ? '' : 's'} ago`
      }

      const renderActivity = () => {
         const list = $('#activity-list')
         if (!list) return
         const items = storedAlbums.slice(0, 3).map(album => ({
            live: true,
            text: `<strong>${album.frames} frames</strong> developed for “${esc(album.title)}”`,
            time: album.createdAt ? timeAgo(album.createdAt) : 'today'
         }))
         items.push(
            { live: false, text: '<strong>18 frames</strong> developed for “Golden Hour”', time: '12 min ago' },
            { live: false, text: 'Grandma Ruth joined the cast — face trained on 6 photos', time: '2 hrs ago' },
            { live: false, text: '<strong>6 frames</strong> saved to the wall from Route 12', time: 'Yesterday' },
            { live: false, text: 'Plus One renewed · receipt sent to your inbox', time: '3 days ago' }
         )
         list.innerHTML = items.map(item => `
            <li>
               <span class="activity__dot${item.live ? ' is-live' : ''}"></span>
               <div>
                  <p>${item.text}</p>
                  <p class="activity__time">${esc(item.time)}</p>
               </div>
            </li>`).join('')
      }

      /* --- people --- */
      const peopleGrid = $('#people-grid')
      const peopleSearch = $('#people-search')
      const personInput = $('#person-input')

      const renderPeople = () => {
         if (!peopleGrid) return
         $$('.person[data-person]', peopleGrid).forEach(node => node.remove())
         const query = state.peopleSearch.trim().toLowerCase()
         const visible = people.filter(person => !query || person.name.toLowerCase().includes(query))
         const addTile = $('.person--add', peopleGrid)
         const fragment = document.createDocumentFragment()

         visible.forEach(person => {
            const card = document.createElement('article')
            card.className = 'person'
            card.dataset.person = 'true'
            card.dataset.name = person.name.toLowerCase()
            card.innerHTML = `
               <div class="person__photo">
                  <img src="${esc(person.image)}" alt="${esc(person.name)}" loading="lazy">
                  <span class="person__lock"><i class="ri-lock-2-line"></i> Face lock</span>
               </div>
               <div class="person__body">
                  ${person.fresh
                     ? `<p class="person__name"><input class="person__rename" value="${esc(person.name)}" aria-label="Name this person"></p>`
                     : `<p class="person__name">${esc(person.name)}</p>`}
                  <p class="person__role">${esc(person.role)}</p>
                  <p class="person__events">${person.events} album${person.events === 1 ? '' : 's'}</p>
               </div>`
            fragment.append(card)
         })

         peopleGrid.insertBefore(fragment, addTile)

         setText('#people-meta', `${people.length} faces · all consented`)
         setText('#stat-people', String(people.length))
      }

      peopleGrid?.addEventListener('input', event => {
         const input = event.target.closest('.person__rename')
         if (!input) return
         const card = input.closest('.person')
         const index = $$('.person[data-person]', peopleGrid).indexOf(card)
         const visible = people.filter(person => !state.peopleSearch.trim() || person.name.toLowerCase().includes(state.peopleSearch.trim().toLowerCase()))
         const person = visible[index]
         if (person) {
            person.name = input.value || 'New face'
            card.dataset.name = person.name.toLowerCase()
         }
      })

      peopleSearch?.addEventListener('input', () => {
         state.peopleSearch = peopleSearch.value
         renderPeople()
      })

      personInput?.addEventListener('change', () => {
         const file = personInput.files?.[0]
         if (!file) return
         const image = URL.createObjectURL(file)
         people.unshift({ name: 'New face', role: 'Just added', events: 0, image, fresh: true })
         if (peopleSearch) peopleSearch.value = ''
         state.peopleSearch = ''
         renderPeople()
         showToast('Face added — give them a name.')
         personInput.value = ''
      })

      /* --- saved wall + lightbox --- */
      const savedGrid = $('#saved-grid')
      const lightbox = $('#lightbox')
      const lightboxImg = $('#lightbox-img')
      const lightboxTitle = $('#lightbox-title')
      const lightboxMeta = $('#lightbox-meta')
      const lightboxDownload = $('#lightbox-download')
      const lightboxClose = $('#lightbox-close')
      let lightboxReturn = null
      let lightboxIndex = 0

      const renderSaved = () => {
         if (!savedGrid) return
         savedGrid.innerHTML = SAVED.map((frame, index) => `
            <figure class="saved">
               <img src="${esc(frame.src)}" alt="${esc(frame.title)}" loading="lazy"
                  style="filter:${frame.filter};transform:scale(${frame.zoom});object-position:${frame.pos}">
               <figcaption class="saved__meta">
                  <b>${esc(frame.title)}</b>
                  <span>${esc(frame.meta)}</span>
               </figcaption>
               <button type="button" class="saved__open" data-open-frame="${index}" aria-label="Open ${esc(frame.title)}"></button>
               <button type="button" class="saved__dl" data-download-frame="${index}" aria-label="Download ${esc(frame.title)}">
                  <i class="ri-download-2-line"></i>
               </button>
            </figure>`).join('')
      }

      const downloadSaved = async (index, button) => {
         const frame = SAVED[index]
         if (!frame || button.disabled) return
         const icon = button.querySelector('i')
         button.disabled = true
         icon.className = 'ri-loader-4-line'

         const result = await window.plusOneDownload.frame({
            src: frame.src,
            filename: `${slugify(frame.title)}.jpg`,
            filter: frame.filter,
            zoom: frame.zoom,
            pos: frame.pos
         })

         icon.className = result === 'failed' ? 'ri-error-warning-line' : 'ri-check-line'
         button.classList.add('is-done')
         if (result === 'baked') showToast('Frame downloaded with its grade baked in.')
         else if (result === 'source') showToast('Frame opened full-size in a new tab — save it from there.')
         else showToast('That frame could not be downloaded.')

         window.setTimeout(() => {
            button.disabled = false
            button.classList.remove('is-done')
            icon.className = 'ri-download-2-line'
         }, 1400)
      }

      const openLightbox = (index, trigger) => {
         const frame = SAVED[index]
         if (!frame || !lightbox) return
         lightboxIndex = index
         lightboxImg.src = frame.src
         lightboxImg.alt = frame.title
         lightboxImg.style.filter = frame.filter
         lightboxImg.style.transform = `scale(${frame.zoom})`
         lightboxImg.style.objectPosition = frame.pos
         lightboxTitle.textContent = frame.title
         lightboxMeta.textContent = frame.meta
         lightbox.setAttribute('aria-hidden', 'false')
         lightbox.classList.add('is-open')
         document.body.style.overflow = 'hidden'
         lightboxReturn = trigger
         lightboxClose.focus()
      }

      const closeLightbox = () => {
         if (!lightbox || !lightbox.classList.contains('is-open')) return
         lightbox.classList.remove('is-open')
         lightbox.setAttribute('aria-hidden', 'true')
         document.body.style.overflow = ''
         if (lightboxReturn && typeof lightboxReturn.focus === 'function') {
            lightboxReturn.focus({ preventScroll: true })
         }
      }

      savedGrid?.addEventListener('click', event => {
         const download = event.target.closest('[data-download-frame]')
         if (download) {
            downloadSaved(Number(download.dataset.downloadFrame), download)
            return
         }
         const open = event.target.closest('[data-open-frame]')
         if (open) openLightbox(Number(open.dataset.openFrame), open)
      })

      lightboxDownload?.addEventListener('click', () => {
         downloadSaved(lightboxIndex, lightboxDownload)
      })

      lightboxClose?.addEventListener('click', closeLightbox)
      lightbox?.querySelector('[data-lightbox-close]')?.addEventListener('click', closeLightbox)
      document.addEventListener('keydown', event => {
         if (event.key === 'Escape') closeLightbox()
      })

      /* --- view switching --- */
      const viewLabels = { overview: 'Overview', albums: 'Albums', people: 'People', wall: 'Wall' }
      const navButtons = $$('.dashnav__item')
      const panels = $$('.dashview')

      const setView = (view, updateHash = true) => {
         const next = viewLabels[view] ? view : 'overview'
         state.view = next
         navButtons.forEach(button => {
            const active = button.dataset.view === next
            button.classList.toggle('is-active', active)
            if (active) button.setAttribute('aria-current', 'page')
            else button.removeAttribute('aria-current')
         })
         panels.forEach(panel => { panel.hidden = panel.dataset.panel !== next })
         setText('#crumb-view', viewLabels[next])
         document.title = `${viewLabels[next]} — Plus One`
         if (updateHash) history.replaceState(null, '', `#${next}`)
         window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' })
      }

      navButtons.forEach(button => {
         button.addEventListener('click', () => setView(button.dataset.view))
      })

      $$('[data-goto]').forEach(button => {
         button.addEventListener('click', () => setView(button.dataset.goto))
      })

      window.addEventListener('hashchange', () => {
         const hash = window.location.hash.replace('#', '')
         if (viewLabels[hash]) setView(hash, false)
      })

      $('#sign-out')?.addEventListener('click', async () => {
         clearSession()
         paintAccount()
         showToast('Signed out. See you at the next roll.')
         await sleep(650)
         window.location.href = 'auth.html'
      })

      /* --- first paint --- */
      renderAlbums()
      renderRecent()
      renderActivity()
      renderPeople()
      renderSaved()

      const initial = window.location.hash.replace('#', '')
      setView(viewLabels[initial] ? initial : 'overview', false)
   }

   /*=============== ROUTER ===============*/
   const page = document.body.dataset.page
   if (page === 'auth') initAuth()
   if (page === 'pricing') initPricing()
   if (page === 'dashboard') initDashboard()
})()
