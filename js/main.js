/*==================== MENU SHOW Y HIDDEN ====================*/
const navMenu = document.getElementById('nav-menu'),
      navToggle = document.getElementById('nav-toggle'),
      navClose = document.getElementById('nav-close');

/*===== MENU SHOW =====*/
/* Validate if constant exists */
if(navToggle){
    navToggle.addEventListener('click', () => {
        navMenu.classList.add('show-menu')
    })
}

/*===== MENU HIDDEN =====*/
/* Validate if constant exists */
if(navClose){
    navClose.addEventListener('click', () => {
        navMenu.classList.remove('show-menu')
    })
}

/*==================== REMOVE MENU MOBILE ====================*/
const navLink = document.querySelectorAll('.nav__link');

function linkAction(){
    const navMenu = document.getElementById('nav-menu')
    // When we click on each nav__link, we remove the show-menu class
    navMenu.classList.remove('show-menu')
}
navLink.forEach(n => n.addEventListener('click', linkAction));

/*==================== MODAL OVERLAYS (shared helpers) ====================*/
function openOverlay(modal){
    closeOverlays()
    modal.classList.add('modal-active')
    document.body.classList.add('no-scroll')
}

function closeOverlays(){
    document.querySelectorAll('.modal-active').forEach((modal) => {
        modal.classList.remove('modal-active')
    })
    document.body.classList.remove('no-scroll')
}

/*==================== SHOW ABOUT ME ====================*/
const aboutBtn = document.querySelector('.about__button')
const aboutModal = document.querySelector('.about__modal')

if(aboutBtn && aboutModal) {
    aboutBtn.addEventListener('click', () => {
        openOverlay(aboutModal)
    })
}

/* Clicking a modal's closing button or CTA must dismiss the overlay */
document.querySelectorAll('.about__modal .modal-close, .about__modal .modal-cta').forEach((btn) => {
    btn.addEventListener('click', () => {
        closeOverlays()
    })
})

/*==================== ACCORDION SKILLS ====================*/
const skillsContent = document.getElementsByClassName('skills__content'),
      skillsHeader = document.querySelectorAll('.skills__header');  

function toggleSkills(){
    let itemClass = this.parentNode.className;

    for(i = 0; i < skillsContent.length; i++){
        skillsContent[i].className = 'skills__content skills__close';
    }
    if(itemClass === 'skills__content skills__close'){
        this.parentNode.className = 'skills__content skills__open';
    }
    syncSkillsAria();
}

function syncSkillsAria(){
    Array.prototype.forEach.call(skillsContent, (card) => {
        const header = card.querySelector('.skills__header')
        if(header) header.setAttribute('aria-expanded', card.classList.contains('skills__open'))
    })
}

skillsHeader.forEach((el) => {
    el.addEventListener('click', toggleSkills);
    el.addEventListener('keydown', (e) => {
        if(e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        toggleSkills.call(el);
    })
});

syncSkillsAria();

/*==================== QUALIFICATION TABS ====================*/
const tabs = document.querySelectorAll('[data-target]'),
      tabContents = document.querySelectorAll('[data-content]')

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const target = document.querySelector(tab.dataset.target)

        tabContents.forEach(tabContent => {
            tabContent.classList.remove('qualification__active')
        })
        target.classList.add('qualification__active')

        tabs.forEach(tab => {
            tab.classList.remove('qualification__active')
        })
        tab.classList.add('qualification__active')
    })
})

/*==================== SHOW QUALIFICATION DETAIL ====================*/
const qualificationModals = document.querySelectorAll('.qualification__modal')

function modalFor(trigger){
    const entry = trigger.closest('.qualification__data')
    return entry ? entry.querySelector('.qualification__modal') : null
}

document.querySelectorAll('.qualification__link, .qualification__details').forEach((trigger) => {
    trigger.addEventListener('click', () => {
        const modal = modalFor(trigger)
        if(modal) openOverlay(modal)
    })
})

qualificationModals.forEach((modal) => {
    /* Backdrop click closes */
    modal.addEventListener('click', (e) => {
        if(e.target === modal) closeOverlays()
    })

    modal.querySelectorAll('.modal-close, .modal-cta').forEach((btn) => {
        btn.addEventListener('click', () => {
            closeOverlays()
        })
    })
})

document.addEventListener('keydown', (e) => {
    if(e.key === 'Escape') closeOverlays()
})


/*==================== SERVICES MODAL ====================*/
const serviceViews = document.querySelectorAll('.services__modal')

document.querySelectorAll('.services__button').forEach((btn) => {
    btn.addEventListener('click', () => {
        const modal = btn.closest('.services__content').querySelector('.services__modal')
        if(modal) openOverlay(modal)
    })
})

serviceViews.forEach((modal) => {
    modal.addEventListener('click', (e) => {
        if(e.target === modal) closeOverlays()
    })

    modal.querySelectorAll('.modal-close, .modal-cta').forEach((btn) => {
        btn.addEventListener('click', () => {
            closeOverlays()
        })
    })
})

/*==================== HERO IMAGE CAROUSEL ====================*/
let swiperHero = new Swiper(".hero-swiper", {
    loop: true,
    grabCursor: true,
    autoplay: {
        delay: 3500,
        disableOnInteraction: false,
    },
    pagination: {
        el: ".hero-swiper-pagination",
        clickable: true,
    },
})

/*==================== PORTFOLIO SWIPER  ====================*/
document.querySelectorAll(".portfolio__container").forEach((container) => {
    new Swiper(container, {
        cssMode: true,
        loop: true,

        navigation: {
            nextEl: container.querySelector(".swiper-button-next"),
            prevEl: container.querySelector(".swiper-button-prev"),
        },
        pagination: {
            el: container.querySelector(".swiper-pagination"),
            clickable: true,
        },
    })
})

/*==================== SHOW PORTFOLIO ====================*/
const projectViews = document.querySelectorAll('.portfolio__modal, .blog__modal')

document.querySelectorAll('.portfolio__button-open').forEach((btn) => {
    btn.addEventListener('click', () => {
        const modal = document.getElementById('pf-' + btn.dataset.project)
        if(modal) openOverlay(modal)
    })
})

/*==================== SHOW BLOG POST ====================*/
document.querySelectorAll('.blog__read').forEach((btn) => {
    btn.addEventListener('click', () => {
        const modal = document.getElementById('bl-' + btn.dataset.post)
        if(modal) openOverlay(modal)
    })
})

projectViews.forEach((modal) => {
    modal.addEventListener('click', (e) => {
        if(e.target === modal) closeOverlays()
    })

    modal.querySelectorAll('.modal-close, .modal-cta').forEach((btn) => {
        btn.addEventListener('click', () => {
            closeOverlays()
        })
    })
})

/*==================== TESTIMONIAL ====================*/
let swiperTestimonial = new Swiper('.testimonial__container', {
    grabCursor: true,
    spaceBetween: 24,

    pagination: {
        el: '.swiper-pagination-testimonial',
        clickable: true,
        dynamicBullets: true,
    },
    breakpoints:{
        768: {
            slidesPerView: 2,
        }
    }
    }
)

/*==================== SCROLL SECTIONS ACTIVE LINK ====================*/
const sections = document.querySelectorAll('section[id]')

function scrollActive(){
    const scrollY = window.pageYOffset

    sections.forEach(current =>{
        const sectionHeight = current.offsetHeight
        const sectionTop = current.offsetTop - 50;
        sectionId = current.getAttribute('id')

        if(scrollY > sectionTop && scrollY <= sectionTop + sectionHeight){
            document.querySelector('.nav__menu a[href*=' + sectionId + ']').classList.add('active-link')
        }else{
            document.querySelector('.nav__menu a[href*=' + sectionId + ']').classList.remove('active-link')
        }
    })
}
window.addEventListener('scroll', scrollActive)

/*==================== CHANGE BACKGROUND HEADER ====================*/ 
function scrollHeader(){
    const nav = document.getElementById('header')
    // When the scroll is greater than 200 viewport height, add the scroll-header class to the header tag
    if(this.scrollY >= 80) nav.classList.add('scroll-header'); else nav.classList.remove('scroll-header')
}
window.addEventListener('scroll', scrollHeader)


/*==================== SHOW SCROLL UP ====================*/ 
function scrollTop(){
    const scrollTop = document.getElementById('scroll-up');
    // When the scroll is higher than 560 viewport height, add the show-scroll class to the a tag with the scroll-top class
    if(this.scrollY >= 560) scrollTop.classList.add('show-scroll'); else scrollTop.classList.remove('show-scroll')
}
window.addEventListener('scroll', scrollTop)

/*==================== DARK LIGHT THEME ====================*/ 
const themeButton = document.getElementById('theme-button')
const darkTheme = 'dark-theme'
const iconTheme = 'uil-sun'

// Previously selected topic (if user selected)
const selectedTheme = localStorage.getItem('selected-theme')
const selectedIcon = localStorage.getItem('selected-icon')

// We obtain the current theme that the interface has by validating the dark-theme class
const getCurrentTheme = () => document.body.classList.contains(darkTheme) ? 'dark' : 'light'
const getCurrentIcon = () => themeButton.classList.contains(iconTheme) ? 'uil-moon' : 'uil-sun'

// We validate if the user previously chose a topic
if (selectedTheme) {
  // If the validation is fulfilled, we ask what the issue was to know if we activated or deactivated the dark
  document.body.classList[selectedTheme === 'dark' ? 'add' : 'remove'](darkTheme)
  themeButton.classList[selectedIcon === 'uil-moon' ? 'add' : 'remove'](iconTheme)
}

// Activate / deactivate the theme manually with the button
themeButton.addEventListener('click', () => {
    // Add or remove the dark / icon theme
    document.body.classList.toggle(darkTheme)
    themeButton.classList.toggle(iconTheme)
    // We save the theme and the current icon that the user chose
    localStorage.setItem('selected-theme', getCurrentTheme())
    localStorage.setItem('selected-icon', getCurrentIcon())
})
/*==================== CV DOWNLOAD DROPDOWN ====================*/
const cvDropdown = document.getElementById('cv-dropdown')

if (cvDropdown) {
    const cvToggle = cvDropdown.querySelector('.cv-dropdown__toggle')
    const cvMenu = cvDropdown.querySelector('.cv-dropdown__menu')

    const closeCvMenu = () => {
        cvMenu.hidden = true
        cvToggle.setAttribute('aria-expanded', 'false')
        cvDropdown.classList.remove('is-open')
    }

    cvToggle.addEventListener('click', (e) => {
        e.stopPropagation()
        if (!cvMenu.hidden) {
            closeCvMenu()
            return
        }
        cvMenu.hidden = false
        cvToggle.setAttribute('aria-expanded', 'true')
        cvDropdown.classList.add('is-open')
    })

    document.addEventListener('click', (e) => {
        if (!cvMenu.hidden && !cvDropdown.contains(e.target)) closeCvMenu()
    })

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !cvMenu.hidden) {
            closeCvMenu()
            cvToggle.focus()
        }
    })

    cvMenu.querySelectorAll('.cv-dropdown__item').forEach((item) => {
        item.addEventListener('click', closeCvMenu)
    })
}
