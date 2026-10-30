/*=============== SHOW MENU ===============*/
const navMenu = document.getElementById('nav-menu'),
      navToggle = document.getElementById('nav-toggle'),
      navClose = document.getElementById('nav-close')

const toggleMenu = show => {
   navMenu.classList.toggle('show-menu', show)
   document.body.classList.toggle('menu-open', show)
   navToggle.setAttribute('aria-expanded', show)
}

if (navToggle) {
   navToggle.addEventListener('click', () => toggleMenu(true))
}

if (navClose) {
   navClose.addEventListener('click', () => toggleMenu(false))
}

/*=============== REMOVE MENU MOBILE ===============*/
const navLink = document.querySelectorAll('.nav__link')

const linkAction = () => toggleMenu(false)
navLink.forEach(n => n.addEventListener('click', linkAction))

/*=============== CHANGE HEADER STYLES ===============*/
const header = document.getElementById('header')
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const scrollHeader = () => {
   this.scrollY >= 50 ? header.classList.add('scroll-header')
                      : header.classList.remove('scroll-header')
}
window.addEventListener('scroll', scrollHeader)
scrollHeader()

/*=============== DECORATIVE WAVEFORMS ===============*/
document.querySelectorAll('[data-bars]').forEach(el => {
   const count = Number(el.dataset.bars) || 16
   const frag = document.createDocumentFragment()

   for (let i = 0; i < count; i++) {
      const bar = document.createElement('i')
      const height = 18 + Math.abs(Math.sin(i * 1.37 + 0.6)) * 74
      bar.style.setProperty('--h', `${height.toFixed(0)}%`)
      bar.style.setProperty('--d', `${(i * 0.06).toFixed(2)}s`)
      frag.appendChild(bar)
   }

   el.appendChild(frag)
})

/*=============== VOICE PREVIEWS (SPEECH SYNTHESIS) ===============*/
const synth = 'speechSynthesis' in window ? window.speechSynthesis : null
let activeButton = null
let systemVoices = []

const loadVoices = () => {
   if (!synth) return
   systemVoices = synth.getVoices()
}
loadVoices()
if (synth) synth.onvoiceschanged = loadVoices

const pickVoice = lang => {
   const exact = systemVoices.find(v => v.lang.replace('_', '-').toLowerCase() === lang.toLowerCase())
   if (exact) return exact
   return systemVoices.find(v => v.lang.toLowerCase().startsWith(lang.split('-')[0].toLowerCase()))
}

const setIcon = (button, playing) => {
   const icon = button.querySelector('i')
   if (!icon) return
   icon.classList.toggle('ri-play-fill', !playing)
   icon.classList.toggle('ri-stop-fill', playing)
}

/* Never let a preview re-enable autoplay for reduced-motion visitors */
const resumeAutoplay = () => {
   if (reduceMotion) return
   if (swiperHome.autoplay && swiperHome.autoplay.running === false) swiperHome.autoplay.start()
}

const stopSpeech = () => {
   if (!synth) return

   synth.cancel()

   if (activeButton) {
      activeButton.classList.remove('is-playing')
      activeButton.closest('.voice-tile, .voice-card')?.classList.remove('is-playing')
      setIcon(activeButton, false)
      activeButton = null
   }

   resumeAutoplay()
}

const previewVoice = button => {
   if (!synth) return

   if (activeButton === button && synth.speaking) {
      stopSpeech()
      return
   }

   stopSpeech()

   const text = button.dataset.text
   if (!text) return

   const utterance = new SpeechSynthesisUtterance(text)
   utterance.lang = button.dataset.lang || 'en-US'
   utterance.pitch = Number(button.dataset.pitch || 1)
   utterance.rate = Number(button.dataset.rate || 1)

   const voice = pickVoice(utterance.lang)
   if (voice) utterance.voice = voice

   utterance.onstart = () => {
      button.classList.add('is-playing')
      button.closest('.voice-tile, .voice-card')?.classList.add('is-playing')
      setIcon(button, true)

      if (button.closest('.home')) swiperHome.autoplay.stop()
   }

   utterance.onend = () => {
      if (activeButton !== button) return
      button.classList.remove('is-playing')
      button.closest('.voice-tile, .voice-card')?.classList.remove('is-playing')
      setIcon(button, false)
      activeButton = null

      resumeAutoplay()
   }

   utterance.onerror = utterance.onend

   activeButton = button
   synth.speak(utterance)
}

document.querySelectorAll('.js-speak').forEach(button => {
   button.addEventListener('click', () => previewVoice(button))
})

// Leaving the tab should never leave a voice talking
document.addEventListener('visibilitychange', () => {
   if (document.hidden && activeButton) stopSpeech()
})

/*=============== SWIPER HOME ===============*/
const swiperHome = new Swiper('.home__swiper', {
   loop: true,
   speed: 1100,
   loopedSlides: 3,
   grabCursor: true,
   effect: 'creative',

   creativeEffect: {
      limitProgress: 3,
      // The voice that just played falls out of frame
      prev: {
         translate: [0, '250%', 0],
      },
      // The next voice waits on the right, smaller
      next: {
         translate: ['225px', 0, 0],
         scale: 0.7,
      },
   },

   breakpoints: {
      548: {
         creativeEffect: {
            next: { translate: ['268px', 0, 0], scale: 0.7 },
         },
      },
      1150: {
         creativeEffect: {
            next: { translate: ['286px', 0, 0], scale: 0.7 },
         },
      },
   },
   navigation: {
      nextEl: '.swiper-button-next',
      prevEl: '.swiper-button-prev',
   },
   autoplay: reduceMotion ? false : {
      delay: 5200,
      disableOnInteraction: false,
   },
})

/* Change background color */
const homeBg = document.querySelectorAll('.home__bg')

swiperHome.on('slideChange', () => {
   // Show only the background of the active voice
   homeBg.forEach(bg => bg.classList.remove('active-bg'))
   homeBg[swiperHome.realIndex].classList.add('active-bg')

   // A preview should not follow us to the next voice
   if (activeButton && activeButton.closest('.home')) stopSpeech()
})

/*=============== VOICE FILTERS ===============*/
const filters = document.querySelectorAll('.filter')
const voiceCards = document.querySelectorAll('.voice-card')

filters.forEach(f => f.setAttribute('aria-pressed', f.classList.contains('is-active')))

filters.forEach(filter => {
   filter.addEventListener('click', () => {
      filters.forEach(f => {
         f.classList.remove('is-active')
         f.setAttribute('aria-pressed', 'false')
      })
      filter.classList.add('is-active')
      filter.setAttribute('aria-pressed', 'true')

      const category = filter.dataset.filter
      let hidingActive = false

      voiceCards.forEach(card => {
         const show = category === 'all' || card.dataset.cat === category
         card.classList.toggle('is-hidden', !show)

         if (!show && card.contains(activeButton)) hidingActive = true
      })

      if (hidingActive) stopSpeech()
   })
})

/*=============== START FORM ===============*/
const startForm = document.getElementById('start-form'),
      startEmail = document.getElementById('start-email'),
      startNote = document.getElementById('start-note')

if (startForm) {
   startForm.addEventListener('submit', event => {
      event.preventDefault()

      if (!startEmail.value || !startEmail.checkValidity()) {
         startNote.textContent = 'Please enter a valid email address.'
         startNote.classList.remove('is-success')
         startNote.classList.add('is-error')
         startEmail.focus()
         return
      }

      const button = startForm.querySelector('button')
      startForm.classList.add('is-sent')
      button.textContent = 'Check your inbox'
      button.disabled = true
      startEmail.disabled = true
      startNote.textContent = 'You are in. Your studio link is on its way.'
      startNote.classList.remove('is-error')
      startNote.classList.add('is-success')
   })
}

/*=============== SCROLL SPY ===============*/
const spyLinks = document.querySelectorAll('.nav__link')

const spy = new IntersectionObserver(entries => {
   entries.forEach(entry => {
      if (!entry.isIntersecting) return

      const id = entry.target.id
      spyLinks.forEach(link => {
         link.classList.toggle('active-link', link.getAttribute('href') === `#${id}`)
      })
   })
}, { rootMargin: '-45% 0px -50% 0px' })

;[...spyLinks].forEach(link => {
   const target = document.querySelector(link.getAttribute('href'))
   if (target) spy.observe(target)
})

/*=============== GSAP ANIMATION ===============*/
if (window.gsap && !reduceMotion) {
   gsap.defaults({ opacity: 0, ease: 'back.out(1.6)', duration: 1.3 })

   const tl = gsap.timeline()
   tl.from('.nav > *', { y: -30 }, 0.3)
     .from('.home__swiper', { y: -180 }, 0.8)
     .from('.home__badge', { y: 80 }, 1.1)
     .from('.home__title', { y: 120 }, 1.2)
     .from('.home__description, .home__buttons', { y: 120 }, 1.4)
     .from('.home__wave', { y: 200, ease: 'back.out(0)' }, 1.7)
     .from('.home__bottom', { y: 200 }, 1.9)
}

/*=============== FOOTER YEAR ===============*/
const year = document.getElementById('year')
if (year) year.textContent = new Date().getFullYear()
