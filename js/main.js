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

/*==================== SHOW ABOUT ME ====================*/
const aboutBtn = document.querySelector('.about__button')
const aboutModal = document.querySelector('.about__modal')
const aboutClose = document.querySelector('.about__modal-close')
const aboutModalLinks = document.querySelectorAll('.about__modal-link')

let about = function(){
    aboutModal.classList.add('about-active')
}

if(aboutBtn) {
    aboutBtn.addEventListener('click', () => {
        aboutModal.classList.add('about-active')
    })
} 

if(aboutClose) {
    aboutClose.addEventListener('click', () => {
        aboutModal.classList.remove('about-active')
    })
}

if(aboutModalLinks.length) {
    aboutModalLinks.forEach((link) => {
        link.addEventListener('click', () => {
            aboutModal.classList.remove('about-active')
        })
    })
}

/*==================== CV DOWNLOAD DROPDOWN ====================*/
const cvDownload = document.querySelector('.cv-download'),
      cvDownloadToggle = document.getElementById('cv-download-toggle'),
      cvDownloadItems = document.querySelectorAll('.cv-download__item');

if(cvDownload && cvDownloadToggle){
    const closeCvMenu = () => {
        cvDownload.classList.remove('cv-download--open');
        cvDownloadToggle.setAttribute('aria-expanded', 'false');
    }

    const openCvMenu = () => {
        cvDownload.classList.remove('cv-download--up');
        cvDownload.classList.add('cv-download--open');
        cvDownloadToggle.setAttribute('aria-expanded', 'true');

        const menuBox = document.getElementById('cv-download-menu').getBoundingClientRect();
        if(menuBox.bottom > window.innerHeight - 16){
            cvDownload.classList.add('cv-download--up');
        }
    }

    cvDownloadToggle.addEventListener('click', () => {
        cvDownload.classList.contains('cv-download--open') ? closeCvMenu() : openCvMenu();
    })

    cvDownloadToggle.addEventListener('keydown', (e) => {
        if(e.key === 'ArrowDown'){
            e.preventDefault();
            openCvMenu();
            cvDownloadItems[0].focus();
        }
    })

    cvDownloadItems.forEach((item, index) => {
        item.addEventListener('click', closeCvMenu);

        item.addEventListener('keydown', (e) => {
            if(e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;

            e.preventDefault();
            const step = e.key === 'ArrowDown' ? 1 : -1;
            const next = (index + step + cvDownloadItems.length) % cvDownloadItems.length;
            cvDownloadItems[next].focus();
        })
    })

    document.addEventListener('click', (e) => {
        if(!cvDownload.contains(e.target)) closeCvMenu();
    });

    document.addEventListener('keydown', (e) => {
        if(e.key === 'Escape'){
            closeCvMenu();
            cvDownloadToggle.focus();
        }
    });
}

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
}

skillsHeader.forEach((el) => {
    el.addEventListener('click', toggleSkills);
});

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

/*==================== SHOW WORK EXPERIENCE ====================*/
const qualificationBtns = document.querySelectorAll('.qualification__link');
const qualificationModalCloseBtns = document.querySelectorAll('.qualification__modal-close');

let closeWork = function(btn){
    const qualificationModal = btn.closest('.qualification__modal');
    qualificationModal.style.opacity = '0';
    qualificationModal.style.visibility = 'hidden';
}

let showWork = function(btn){
    const qualificationModal = btn.closest('.qualification__data').querySelector('.qualification__modal');
    qualificationModal.style.opacity = '1';
    qualificationModal.style.visibility = 'visible';
}

qualificationBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
        showWork(btn)
    })
})

qualificationModalCloseBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
        closeWork(btn)
    })
})

document.querySelectorAll('.qualification__contact-link').forEach((link) => {
    link.addEventListener('click', () => {
        closeWork(link)
    })
})


/*==================== SERVICES MODAL ====================*/
const modalViews = document.querySelectorAll('.services__modal'),
      modalBtns = document.querySelectorAll('.services__button'),
      modalCloses = document.querySelectorAll('.services__modal-close')

let modal = function(modalClick){
    modalViews[modalClick].classList.add('active-modal')
}

modalBtns.forEach((modalBtn, i) => {
    modalBtn.addEventListener('click', () => {
        modal(i)
    })
})

modalCloses.forEach((modalClose) => {
    modalClose.addEventListener('click', () => {
        modalViews.forEach((modalView) => {
            modalView.classList.remove('active-modal')
        })
    })
})

document.querySelectorAll('.services__contact-link').forEach((link) => {
    link.addEventListener('click', () => {
        link.closest('.services__modal').classList.remove('active-modal')
    })
})

/*==================== PORTFOLIO SWIPER  ====================*/
var swiper = new Swiper(".portfolio__container", {
    cssMode: true,
    loop: true,

    navigation: {
      nextEl: ".swiper-button-next",
      prevEl: ".swiper-button-prev",
    },
    pagination: {
      el: ".swiper-pagination",
      clickable: true,
    },
})

/*==================== SHOW PORTFOLIO ====================*/
const portfolioBtns = document.querySelectorAll('.portfolio__button-open');
const portfolioModalCloseBtns = document.querySelectorAll('.portfolio__modal-close');

let closePortfolio = function(btn){
    const portfolioModal = btn.closest('.portfolio__modal');
    portfolioModal.classList.remove('modal-active')
}

const portfolioCarousels = new WeakMap()

let initPortfolioCarousel = function(modal){
    const carousel = modal.querySelector('.detail-carousel')
    if (!carousel) return

    if (portfolioCarousels.has(carousel)) {
        portfolioCarousels.get(carousel).update()
        return
    }

    const instance = new Swiper(carousel, {
        loop: carousel.querySelectorAll('.swiper-slide').length > 1,
        watchOverflow: true,
        grabCursor: true,
        spaceBetween: 8,
        pagination: {
            el: carousel.querySelector('.detail-carousel__dots'),
            clickable: true,
        },
        navigation: {
            nextEl: carousel.querySelector('.detail-carousel__next'),
            prevEl: carousel.querySelector('.detail-carousel__prev'),
        },
    })

    portfolioCarousels.set(carousel, instance)
}

let showPortfolio = function(btn){
    const portfolioModal = document.getElementById(btn.dataset.portfolioTarget)
    if (!portfolioModal) return

    portfolioModal.classList.add('modal-active')
    initPortfolioCarousel(portfolioModal)
}

portfolioBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
        showPortfolio(btn)
    })

    btn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            showPortfolio(btn)
        }
    })
})

portfolioModalCloseBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
        closePortfolio(btn)
    })
})

document.querySelectorAll('.portfolio__contact-link').forEach((link) => {
    link.addEventListener('click', () => {
        closePortfolio(link)
    })
})

/*==================== TESTIMONIAL ====================*/
let swiperTestimonial = new Swiper('.testimonial__container', {
    loop: true,
    grabCursor: true,
    spaceBetween: 24,

    pagination: {
        el: '.swiper-pagination',
        clickable: true,
        dynamicBullets: true,
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