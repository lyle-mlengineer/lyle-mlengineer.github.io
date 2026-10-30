/*=============== SHOW MENU ===============*/
const nav = document.querySelector('.nav')
const navMenu = document.getElementById('nav-menu')
const navToggle = document.getElementById('nav-toggle')
const navClose = document.getElementById('nav-close')

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

document.querySelectorAll('.nav__link, .nav__cta').forEach(link => {
   link.addEventListener('click', closeMenu)
})

document.addEventListener('keydown', event => {
   if (event.key === 'Escape' && navMenu.classList.contains('show-menu')) closeMenu()
})

/*=============== HERO SLIDER ===============*/
const slideCurrent = document.getElementById('slide-current')

const swiperHome = new Swiper('.home__swiper', {
   loop: true,
   speed: 900,
   effect: 'fade',
   fadeEffect: { crossFade: true },
   grabCursor: true,
   autoplay: {
      delay: 6200,
      disableOnInteraction: false,
      pauseOnMouseEnter: true
   },
   navigation: {
      nextEl: '.home__arrow.swiper-button-next',
      prevEl: '.home__arrow.swiper-button-prev'
   }
})

swiperHome.on('slideChange', () => {
   slideCurrent.textContent = String(swiperHome.realIndex + 1).padStart(2, '0')
})

/*=============== HEADER ON SCROLL ===============*/
const header = document.getElementById('header')

const scrollHeader = () => {
   header.classList.toggle('scroll-header', window.scrollY >= 40)
}
window.addEventListener('scroll', scrollHeader, { passive: true })
scrollHeader()

/*=============== ALBUM TABS ===============*/
const albums = {
   wedding: {
      venue: 'Golden Hour Farm, Hudson Valley',
      date: 'Saturday 14 June · golden hour 8:14 pm',
      people: 9,
      activities: 12,
      frames: 148,
      list: [
         { name: 'Ceremony', time: '4:00 pm' },
         { name: 'Confetti on the lawn', time: '4:52 pm' },
         { name: 'First dance', time: '8:36 pm', latest: true },
         { name: 'The toast', time: '8:58 pm' }
      ],
      shots: [
         { src: 'img/event-wedding.jpg', alt: 'Bride and groom dancing under string lights', caption: 'First dance · 8:36 pm' },
         { src: 'img/wed-confetti.jpg', alt: 'Newlyweds walking through confetti', caption: 'Confetti · 4:52 pm' },
         { src: 'img/wed-toast.jpg', alt: 'Wedding guests raising a toast', caption: 'The toast · 8:58 pm' }
      ]
   },
   roadtrip: {
      venue: 'Route 12, Escalante, Utah',
      date: 'Friday 3 May · last light 8:02 pm',
      people: 7,
      activities: 9,
      frames: 63,
      list: [
         { name: 'Packing the wagon', time: '6:40 am' },
         { name: 'Gas stop', time: '11:42 am' },
         { name: 'Hair out the window', time: '4:36 pm' },
         { name: 'The lookout', time: '7:20 pm', latest: true }
      ],
      shots: [
         { src: 'img/event-roadtrip.jpg', alt: 'Two friends laughing on a station wagon tailgate', caption: 'The lookout · 7:20 pm' },
         { src: 'img/rt-gas.jpg', alt: 'Friends buying snacks at a gas station', caption: 'Gas stop · 11:42 am' },
         { src: 'img/rt-window.jpg', alt: 'A woman with her hair out the car window', caption: 'Hair out the window · 4:36 pm' }
      ]
   },
   graduation: {
      venue: 'Whitman Quad, Chapel Hill',
      date: 'Sunday 11 May · 1:30 pm',
      people: 6,
      activities: 7,
      frames: 96,
      list: [
         { name: 'The walk across the quad', time: '1:32 pm' },
         { name: 'Cap toss', time: '1:58 pm' },
         { name: 'Family, after', time: '2:40 pm', latest: true },
         { name: 'Dinner downtown', time: '6:15 pm' }
      ],
      shots: [
         { src: 'img/event-graduation.jpg', alt: 'A graduate hugging her mother while caps fly', caption: 'After the ceremony · 2:11 pm' },
         { src: 'img/grad-cap.jpg', alt: 'A graduate throwing her cap into the sky', caption: 'Cap toss · 1:58 pm' },
         { src: 'img/grad-family.jpg', alt: 'A family hugging the graduate', caption: 'Family · 2:40 pm' }
      ]
   },
   picnic: {
      venue: 'Prospect Park, Brooklyn',
      date: 'Sunday 8 September · 2:30 pm',
      people: 11,
      activities: 6,
      frames: 74,
      list: [
         { name: 'The blanket', time: '2:47 pm' },
         { name: 'Lemonade', time: '3:05 pm', latest: true },
         { name: 'Frisbee', time: '3:52 pm' },
         { name: 'Golden hour', time: '6:20 pm' }
      ],
      shots: [
         { src: 'img/event-picnic.jpg', alt: 'A family laughing on a picnic blanket', caption: 'The blanket · 3:05 pm' },
         { src: 'img/pic-frisbee.jpg', alt: 'A girl leaping to catch a frisbee', caption: 'Frisbee · 3:52 pm' },
         { src: 'img/pic-lemonade.jpg', alt: 'A grandmother pouring lemonade', caption: 'Lemonade · 2:47 pm' }
      ]
   }
}

const tabs = document.querySelectorAll('.tab')
const albumPanel = document.getElementById('album-panel')
const albumGrid = document.getElementById('album-grid')
const albumVenue = document.getElementById('album-venue')
const albumDate = document.getElementById('album-date')
const albumPeople = document.getElementById('album-people')
const albumActivities = document.getElementById('album-activities')
const albumFrames = document.getElementById('album-frames')
const albumList = document.getElementById('album-list')
const shotImages = albumGrid.querySelectorAll('img')
const shotCaptions = albumGrid.querySelectorAll('figcaption')

// Warm the cache so a tab switch never shows a half-loaded frame
Object.values(albums).forEach(album => {
   album.shots.forEach(shot => {
      const preload = new Image()
      preload.src = shot.src
   })
})

const setAlbum = key => {
   const album = albums[key]
   if (!album) return

   albumGrid.classList.add('is-swapping')

   window.setTimeout(() => {
      albumVenue.textContent = album.venue
      albumDate.textContent = album.date
      albumPeople.textContent = album.people
      albumActivities.textContent = album.activities
      albumFrames.textContent = album.frames

      albumList.innerHTML = album.list.map(item => `
         <li class="${item.latest ? 'is-latest' : ''}">
            <span>${item.name}</span>
            <time>${item.time}</time>
         </li>
      `).join('')

      album.shots.forEach((shot, index) => {
         shotImages[index].src = shot.src
         shotImages[index].alt = shot.alt
         shotCaptions[index].textContent = shot.caption
      })

      albumGrid.classList.remove('is-swapping')
   }, 220)
}

tabs.forEach(tab => {
   tab.addEventListener('click', () => {
      if (tab.classList.contains('is-active')) return

      tabs.forEach(other => {
         other.classList.remove('is-active')
         other.setAttribute('aria-selected', 'false')
      })
      tab.classList.add('is-active')
      tab.setAttribute('aria-selected', 'true')
      albumPanel.setAttribute('aria-labelledby', tab.id)

      setAlbum(tab.dataset.event)
   })
})

// Fill the activity list for the album that is already visible
const initialAlbum = document.querySelector('.tab.is-active').dataset.event
albumList.innerHTML = albums[initialAlbum].list.map(item => `
   <li class="${item.latest ? 'is-latest' : ''}">
      <span>${item.name}</span>
      <time>${item.time}</time>
   </li>
`).join('')

/*=============== SCROLL REVEAL ===============*/
const revealItems = document.querySelectorAll('[data-reveal]')

if ('IntersectionObserver' in window) {
   const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
         if (!entry.isIntersecting) return
         entry.target.classList.add('is-in')
         observer.unobserve(entry.target)
      })
   }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' })

   revealItems.forEach(item => revealObserver.observe(item))
} else {
   revealItems.forEach(item => item.classList.add('is-in'))
}

/*=============== FAQ ===============*/
const faqItems = document.querySelectorAll('.faq__item')

faqItems.forEach(item => {
   item.addEventListener('toggle', () => {
      if (!item.open) return
      faqItems.forEach(other => {
         if (other !== item) other.open = false
      })
   })
})

/*=============== START FORM ===============*/
const startForm = document.getElementById('start-form')
const startEmail = document.getElementById('start-email')
const startNote = document.getElementById('start-note')

startForm.addEventListener('submit', event => {
   event.preventDefault()
   const email = startEmail.value.trim()

   if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
      startNote.textContent = 'That email looks a little off — mind checking it?'
      startNote.classList.add('is-error')
      startEmail.focus()
      return
   }

   startNote.classList.remove('is-error')
   startNote.classList.add('is-done')
   startNote.textContent = 'Invitation requested — we’ll email the link before your next event.'
   startForm.innerHTML = `
      <p class="start__done">You’re on the list, ${email}<i class="ri-check-line"></i></p>
   `
})

/*=============== INTRO ANIMATION ===============*/
if (window.gsap) {
   gsap.defaults({ ease: 'power3.out', duration: 1.1 })

   const intro = gsap.timeline({ delay: 0.1 })

   intro
      .from('.nav__logo, .nav__list li, .nav__cta', { y: -14, opacity: 0, stagger: 0.05, duration: 0.8 }, 0)
      .from('.home .swiper-slide-active .home__photo', { y: 34, opacity: 0, duration: 1.4 }, 0.25)
      .from('.home .swiper-slide-active .home__snap', { y: 22, opacity: 0, stagger: 0.12, duration: 1 }, 0.55)
      .from('.home .swiper-slide-active .home__kicker', { y: 16, opacity: 0, duration: 0.8 }, 0.65)
      .from('.home .swiper-slide-active .home__title', { y: 26, opacity: 0, duration: 1 }, 0.75)
      .from('.home .swiper-slide-active .home__desc, .home .swiper-slide-active .home__guests, .home .swiper-slide-active .home__actions', { y: 18, opacity: 0, stagger: 0.1, duration: 0.9 }, 0.9)
      .from('.home__hud > *', { y: 12, opacity: 0, stagger: 0.08, duration: 0.8 }, 1.15)
}
