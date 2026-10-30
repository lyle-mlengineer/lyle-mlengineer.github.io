/*=============== STUDIO PAGE ===============*/
(() => {
   'use strict'

   const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
   const header = document.getElementById('header')

   /*=============== MENU ===============*/
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

   const scrollHeader = () => {
      header.classList.toggle('scroll-header', window.scrollY >= 40)
   }
   window.addEventListener('scroll', scrollHeader, { passive: true })
   scrollHeader()

   /*=============== DATA ===============*/
   const OCCASIONS = {
      wedding: {
         label: 'Wedding',
         presets: ['Ceremony', 'Confetti', 'The first dance', 'The toast', 'Cake cutting', 'Speeches'],
         fallback: 'Nobody looked at the camera. That was the whole point.',
         bank: [
            { src: 'img/event-wedding.jpg', alt: 'A bride and groom dancing under string lights at an outdoor wedding' },
            { src: 'img/wed-confetti.jpg', alt: 'Newlyweds walking through a shower of confetti' },
            { src: 'img/wed-toast.jpg', alt: 'Wedding guests raising their glasses at the reception table' }
         ]
      },
      roadtrip: {
         label: 'Road trip',
         presets: ['Packing the car', 'Gas stop', 'Road snacks', 'Hair out the window', 'The lookout', 'Last light'],
         fallback: 'The windows down, the map wrong, nobody in a hurry.',
         bank: [
            { src: 'img/event-roadtrip.jpg', alt: 'Two friends laughing on the tailgate of a station wagon' },
            { src: 'img/rt-gas.jpg', alt: 'Friends buying snacks at a gas station at dusk' },
            { src: 'img/rt-window.jpg', alt: 'A woman with her hair out of the car window on a desert road' }
         ]
      },
      graduation: {
         label: 'Graduation',
         presets: ['The walk across', 'Cap toss', 'Family photos', 'The diploma', 'Dinner downtown', 'Last drinks'],
         fallback: 'Four years of work, one afternoon of relief.',
         bank: [
            { src: 'img/event-graduation.jpg', alt: 'A graduate hugging her mother while caps fly' },
            { src: 'img/grad-cap.jpg', alt: 'A graduate throwing her cap into the sky' },
            { src: 'img/grad-family.jpg', alt: 'A family hugging the graduate on campus' }
         ]
      },
      picnic: {
         label: 'Picnic',
         presets: ['The blanket', 'Lemonade', 'Frisbee', 'Card game', 'Golden hour', 'Packing up'],
         fallback: 'One blanket, too much food, nobody checking the time.',
         bank: [
            { src: 'img/event-picnic.jpg', alt: 'A family laughing together on a picnic blanket' },
            { src: 'img/pic-frisbee.jpg', alt: 'A girl leaping to catch a frisbee in a park' },
            { src: 'img/pic-lemonade.jpg', alt: 'A grandmother pouring lemonade at a picnic' }
         ]
      }
   }

   const GRADES = [
      { b: 1.02, c: 1.01, s: 1.03, sep: 0.02, g: 0, h: 0, z: 1.01, pos: '50% 45%' },
      { b: 0.99, c: 1.05, s: 1.08, sep: 0.08, g: 0, h: -3, z: 1.06, pos: '50% 38%' },
      { b: 1.04, c: 1.03, s: 0.95, sep: 0.02, g: 0.08, h: 0, z: 1.1, pos: '46% 55%' },
      { b: 1, c: 1.1, s: 1.1, sep: 0, g: 0, h: 0, z: 1.02, pos: '54% 50%' },
      { b: 1.02, c: 0.98, s: 0.9, sep: 0.14, g: 0.18, h: 2, z: 1.07, pos: '50% 60%' }
   ]

   const EDIT_RULES = [
      {
         re: /\b(black\s*(?:and|&)\s*white|b\s*&\s*w|bw|mono\w*|gr[ae]yscale)\b/i,
         label: 'black and white',
         apply: s => { s.g = 1; s.c = Math.min(s.c + 0.1, 1.4) }
      },
      {
         re: /\b(warm\w*|gold\w*|sunset|cozy|cosy)\b/i,
         label: 'warmer light',
         apply: s => { s.sep = Math.min(s.sep + 0.14, 0.5); s.s = Math.min(s.s + 0.1, 1.5); s.h -= 5 }
      },
      {
         re: /\b(cool\w*|cold\w*|blue|moon\w*)\b/i,
         label: 'cooler shadow',
         apply: s => { s.h += 7; s.b = Math.max(s.b - 0.05, 0.7); s.s = Math.max(s.s - 0.06, 0.7) }
      },
      {
         re: /\b(bright\w*|lighter|light|expose\w*)\b/i,
         label: 'a stop brighter',
         apply: s => { s.b = Math.min(s.b + 0.12, 1.35) }
      },
      {
         re: /\b(dark\w*|moody|deeper|shadow\w*)\b/i,
         label: 'deeper shadows',
         apply: s => { s.b = Math.max(s.b - 0.1, 0.6); s.c = Math.min(s.c + 0.06, 1.4) }
      },
      {
         re: /\b(contrast\w*|punch\w*|pop|crisp\w*)\b/i,
         label: 'more contrast',
         apply: s => { s.c = Math.min(s.c + 0.12, 1.4); s.s = Math.min(s.s + 0.05, 1.5) }
      },
      {
         re: /\b(fade[ds]?|soft\w*|film\w*|vintage|matte)\b/i,
         label: 'a faded film look',
         apply: s => { s.c = Math.max(s.c - 0.1, 0.75); s.s = Math.max(s.s - 0.08, 0.6); s.sep = Math.min(s.sep + 0.1, 0.45) }
      },
      {
         re: /\b(crop\w*|closer|tight\w*|zoom\w*|close)\b/i,
         label: 'a tighter crop',
         apply: s => { s.z = Math.min(s.z + 0.16, 1.5) }
      },
      {
         re: /\b(wider|pull\w*|room\w*|looser)\b/i,
         label: 'more room around them',
         apply: s => { s.z = Math.max(s.z - 0.12, 1) }
      }
   ]

   const JUMP = /\b(another|different|retake|reshoot|new angle|other angle)\b/i
   const MARK = `
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
         <circle cx="12" cy="12" r="9.1" stroke="currentColor" stroke-width="1.3"/>
         <path d="M12 7.9v8.2M7.9 12h8.2" stroke="currentColor" stroke-width="1.3"/>
      </svg>`
   const OPENERS = [
      'Shot on the day’s own light. Say “warmer”, “mono” or “closer crop” to rework it.',
      'No one was told to smile. Comment an edit and I’ll develop this frame again.',
      'Straight off the roll. Try “another angle”, “brighter” or “black and white”.',
      'From the edge of the moment. Tell me what to change and this frame gets a new pass.'
   ]

   const esc = value => String(value).replace(/[&<>"']/g, ch => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
   })[ch])

   const MAX_FILES = 8
   const MAX_ACTIVITIES = 8

   /*=============== FORM REFS ===============*/
   const form = document.getElementById('brief-form')
   const drop = document.getElementById('drop')
   const fileInput = document.getElementById('seed-input')
   const previews = document.getElementById('previews')
   const seedCount = document.getElementById('seed-count')
   const tagsEl = document.getElementById('tags')
   const activityInput = document.getElementById('activity-input')
   const activityAdd = document.getElementById('activity-add')
   const suggests = document.getElementById('suggests')
   const titleInput = document.getElementById('event-title')
   const venueInput = document.getElementById('venue')
   const briefText = document.getElementById('brief-text')
   const titleError = document.getElementById('title-error')
   const venueError = document.getElementById('venue-error')
   const activityError = document.getElementById('activity-error')
   const briefNote = document.getElementById('brief-note')
   const sampleBtn = document.getElementById('sample-fill')
   const occasionRadios = document.querySelectorAll('input[name="occasion"]')

   const state = {
      occasion: 'wedding',
      activities: [],
      uploads: [],
      album: null,
      posts: [],
      saved: [],
      generating: false,
      epoch: 0
   }

   /*=============== UPLOAD & PREVIEW ===============*/
   const addFiles = fileList => {
      const files = Array.from(fileList).filter(file => file.type.startsWith('image/'))
      if (!files.length) return

      const room = MAX_FILES - state.uploads.length
      if (room <= 0) {
         showToast(`That’s all ${MAX_FILES} frames — remove one to swap it out.`)
         return
      }

      files.slice(0, room).forEach(file => {
         state.uploads.push({
            src: URL.createObjectURL(file),
            name: file.name
         })
      })

      if (files.length > room) {
         showToast(`Only ${MAX_FILES} photos fit in one roll — the first ${room} went in.`)
      }

      renderPreviews()
   }

   const renderPreviews = () => {
      previews.innerHTML = ''
      state.uploads.forEach((upload, index) => {
         const item = document.createElement('li')
         item.className = 'preview'

         const img = document.createElement('img')
         img.src = upload.src
         img.alt = ''

         const remove = document.createElement('button')
         remove.type = 'button'
         remove.className = 'preview__remove'
         remove.setAttribute('aria-label', `Remove ${upload.name}`)
         remove.innerHTML = '<i class="ri-close-line"></i>'
         remove.addEventListener('click', () => {
            const inAlbum = state.album && state.album.sources.some(source => source.src === upload.src)
            if (!inAlbum) URL.revokeObjectURL(upload.src)
            state.uploads.splice(index, 1)
            renderPreviews()
         })

         item.append(img, remove)
         previews.append(item)
      })

      previews.hidden = state.uploads.length === 0
      seedCount.textContent = `${state.uploads.length} of ${MAX_FILES}`
   }

   fileInput.addEventListener('change', () => {
      addFiles(fileInput.files)
      fileInput.value = ''
   })

   ;['dragenter', 'dragover'].forEach(type => {
      drop.addEventListener(type, event => {
         event.preventDefault()
         drop.classList.add('is-over')
      })
   })

   ;['dragleave', 'drop'].forEach(type => {
      drop.addEventListener(type, event => {
         event.preventDefault()
         drop.classList.remove('is-over')
      })
   })

   drop.addEventListener('drop', event => {
      if (event.dataTransfer && event.dataTransfer.files.length) addFiles(event.dataTransfer.files)
   })

   /*=============== OCCASION & ACTIVITIES ===============*/
   const renderTags = () => {
      tagsEl.innerHTML = ''
      state.activities.forEach((activity, index) => {
         const tag = document.createElement('li')
         tag.className = 'tag'

         const label = document.createElement('span')
         label.textContent = activity

         const remove = document.createElement('button')
         remove.type = 'button'
         remove.setAttribute('aria-label', `Remove ${activity}`)
         remove.innerHTML = '<i class="ri-close-line"></i>'
         remove.addEventListener('click', () => {
            state.activities.splice(index, 1)
            renderTags()
            renderSuggests()
         })

         tag.append(label, remove)
         tagsEl.append(tag)
      })
   }

   const renderSuggests = () => {
      const presets = OCCASIONS[state.occasion].presets
      const options = presets.filter(preset => !state.activities.includes(preset) && !state.activities.some(a => a.toLowerCase() === preset.toLowerCase()))
      suggests.innerHTML = ''

      if (!options.length) return

      const label = document.createElement('span')
      label.className = 'suggests__label'
      label.textContent = 'Try'
      suggests.append(label)

      options.slice(0, 4).forEach(option => {
         const button = document.createElement('button')
         button.type = 'button'
         button.textContent = `+ ${option}`
         button.addEventListener('click', () => addActivity(option))
         suggests.append(button)
      })
   }

   const addActivity = name => {
      const value = name.trim()
      if (!value) return
      if (state.activities.some(activity => activity.toLowerCase() === value.toLowerCase())) {
         activityInput.value = ''
         return
      }
      if (state.activities.length >= MAX_ACTIVITIES) {
         showToast(`Eight activities is a full roll — remove one to add another.`)
         return
      }
      state.activities.push(value)
      activityInput.value = ''
      activityError.hidden = true
      activityInput.classList.remove('is-invalid')
      renderTags()
      renderSuggests()
   }

   activityAdd.addEventListener('click', () => addActivity(activityInput.value))

   activityInput.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ',') {
         event.preventDefault()
         addActivity(activityInput.value)
      }
      if (event.key === 'Backspace' && !activityInput.value && state.activities.length) {
         state.activities.pop()
         renderTags()
         renderSuggests()
      }
   })

   activityInput.addEventListener('blur', () => addActivity(activityInput.value))

   const setOccasion = key => {
      if (!OCCASIONS[key] || key === state.occasion) return
      const previousPresets = OCCASIONS[state.occasion].presets
      const usingPresets = state.activities.every(activity => previousPresets.includes(activity))

      state.occasion = key
      if (usingPresets) {
         state.activities = OCCASIONS[key].presets.slice(0, 3)
         renderTags()
      }
      renderSuggests()
   }

   occasionRadios.forEach(radio => {
      radio.addEventListener('change', () => {
         if (radio.checked) setOccasion(radio.value)
      })
   })

   state.activities = OCCASIONS.wedding.presets.slice(0, 3)
   renderTags()
   renderSuggests()
   renderPreviews()

   /* Prefill from dashboard links: studio.html?occasion=…&title=…&venue=… */
   const params = new URLSearchParams(location.search)
   const wantedOccasion = params.get('occasion')
   if (wantedOccasion && OCCASIONS[wantedOccasion]) {
      state.occasion = wantedOccasion
      const radio = document.querySelector(`input[name="occasion"][value="${wantedOccasion}"]`)
      if (radio) radio.checked = true

      const wantedActivities = params.get('activities')
      const parsed = wantedActivities
         ? wantedActivities.split(',').map(activity => activity.trim()).filter(Boolean)
         : []
      state.activities = (parsed.length ? parsed : OCCASIONS[wantedOccasion].presets.slice(0, 3)).slice(0, MAX_ACTIVITIES)
      renderTags()
      renderSuggests()
   }
   if (params.get('title')) titleInput.value = params.get('title')
   if (params.get('venue')) venueInput.value = params.get('venue')
   if (params.get('brief')) briefText.value = params.get('brief')

   /*=============== VALIDATION ===============*/
   const setError = (input, node, message) => {
      node.textContent = message
      node.hidden = !message
      if (input) input.classList.toggle('is-invalid', Boolean(message))
   }

   titleInput.addEventListener('input', () => setError(titleInput, titleError, ''))
   venueInput.addEventListener('input', () => setError(venueInput, venueError, ''))

   const validate = () => {
      let firstInvalid = null

      if (!titleInput.value.trim()) {
         setError(titleInput, titleError, 'Give the roll a title.')
         firstInvalid = firstInvalid || titleInput
      } else {
         setError(titleInput, titleError, '')
      }

      if (!venueInput.value.trim()) {
         setError(venueInput, venueError, 'Where did it happen?')
         firstInvalid = firstInvalid || venueInput
      } else {
         setError(venueInput, venueError, '')
      }

      if (!state.activities.length) {
         setError(activityInput, activityError, 'Add at least one activity.')
         firstInvalid = firstInvalid || activityInput
      } else {
         setError(activityInput, activityError, '')
      }

      if (firstInvalid) {
         firstInvalid.focus({ preventScroll: false })
         firstInvalid.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
      }

      return !firstInvalid
   }

   /*=============== FEED REFS ===============*/
   const feedSection = document.getElementById('feed-section')
   const feedEl = document.getElementById('feed')
   const feedTitle = document.getElementById('feed-title')
   const feedMeta = document.getElementById('feed-meta')
   const feedChips = document.getElementById('feed-chips')
   const feedFrames = document.getElementById('feed-frames')
   const feedMore = document.querySelector('.feed__more')

   /*=============== SAMPLE DAY ===============*/
   sampleBtn.addEventListener('click', () => {
      state.occasion = 'picnic'
      state.activities = OCCASIONS.picnic.presets.slice(0, 4)
      document.querySelector('input[name="occasion"][value="picnic"]').checked = true

      titleInput.value = 'Slow Sunday in the park'
      venueInput.value = 'Prospect Park, Brooklyn'
      briefText.value = 'Four generations on one blanket, lemonade going warm, a frisbee that nearly took out the stroller. Grandma held court until the light went.'

      setError(titleInput, titleError, '')
      setError(venueInput, venueError, '')
      setError(activityInput, activityError, '')
      renderTags()
      renderSuggests()
      form.requestSubmit()
   })

   /*=============== BUILD THE ALBUM ===============*/
   const ALBUM_STORE = 'plusone:albums'

   const rememberAlbum = () => {
      if (!state.album) return
      try {
         const entry = {
            id: state.album.id,
            title: state.album.title,
            venue: state.album.venue,
            occasion: state.album.occasionKey,
            occasionLabel: state.album.occasion.label,
            activities: state.album.activities.slice(0, 6),
            frames: state.posts.length,
            people: state.uploads.length || 4,
            cover: state.album.cover,
            createdAt: state.album.createdAt
         }
         const saved = JSON.parse(localStorage.getItem(ALBUM_STORE) || '[]')
         const rest = Array.isArray(saved) ? saved.filter(album => album.id !== entry.id) : []
         localStorage.setItem(ALBUM_STORE, JSON.stringify([entry, ...rest].slice(0, 8)))
      } catch {
         /* storage can be unavailable in private or file contexts — the feed still works */
      }
   }

   const buildAlbum = () => {
      const occasion = OCCASIONS[state.occasion]
      const sources = state.uploads.length
         ? state.uploads.map(upload => ({ src: upload.src, alt: 'A frame developed from one of your uploaded photos' }))
         : occasion.bank

      state.album = {
         id: `roll-${Date.now()}`,
         createdAt: new Date().toISOString(),
         title: titleInput.value.trim(),
         venue: venueInput.value.trim(),
         occasion,
         occasionKey: state.occasion,
         activities: state.activities.slice(),
         description: briefText.value.trim(),
         sources,
         cover: sources[0].src.startsWith('blob:') ? occasion.bank[0].src : sources[0].src
      }

      state.posts = []
      state.saved = []
      state.generating = false
      state.epoch += 1
      feedEl.innerHTML = ''
      feedTitle.textContent = state.album.title
      feedMeta.innerHTML = `
         <span>${esc(state.album.venue)}</span>
         <span>${esc(occasion.label)}</span>
         <span>${esc(new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }))}</span>
      `

      feedChips.innerHTML = state.album.activities.slice(0, 5)
         .map(activity => `<li>${esc(activity)}</li>`)
         .join('')
      if (state.album.activities.length > 5) {
         feedChips.insertAdjacentHTML('beforeend', `<li>+${state.album.activities.length - 5} more</li>`)
      }

      updateFrames()
      updateSaveCounts()
      renderWall()
      rememberAlbum()
      feedSection.hidden = false
      briefNote.textContent = 'Roll developing — like, save or comment on any frame.'
      briefNote.classList.add('is-live')

      window.requestAnimationFrame(() => {
         feedSection.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
         feedTitle.focus({ preventScroll: true })
      })

      appendBatch(4)
   }

   form.addEventListener('submit', event => {
      event.preventDefault()
      if (!validate()) return
      buildAlbum()
   })

   /*=============== FEED GENERATION ===============*/
   const frameTime = index => {
      const total = 11 * 60 + 20 + index * 23
      const hours24 = Math.floor(total / 60) % 24
      const minutes = total % 60
      const hours12 = ((hours24 + 11) % 12) + 1
      return `${hours12}:${String(minutes).padStart(2, '0')} ${hours24 < 12 ? 'am' : 'pm'}`
   }

   const timeAgo = index => index === 0 ? 'just now' : `${index + 1} min ago`

   const briefFragment = (index, activity) => {
      const description = state.album.description
      if (description) {
         const parts = description
            .split(/(?:[.!?]\s+)|(?:\s+[—–]\s+)|(?:,\s+)/)
            .map(part => part.trim())
            .filter(part => part.length > 10)

         if (parts.length) {
            const key = activity.toLowerCase().replace(/^the\s+/, '')
            const fresh = parts.filter(part => key.length < 4 || !part.toLowerCase().includes(key))
            const pool = fresh.length ? fresh : parts
            const fragment = pool[index % pool.length].replace(/[.!?]+$/, '')
            return `${fragment.charAt(0).toUpperCase()}${fragment.slice(1)}.`
         }
      }
      return state.album.occasion.fallback
   }

   const applyMedia = post => {
      const grade = post.grade
      post.refs.img.style.filter = `brightness(${grade.b.toFixed(3)}) contrast(${grade.c.toFixed(3)}) saturate(${grade.s.toFixed(3)}) sepia(${grade.sep.toFixed(3)}) grayscale(${grade.g.toFixed(3)}) hue-rotate(${grade.h}deg)`
      post.refs.img.style.transform = `scale(${grade.z.toFixed(3)})`
      post.refs.img.style.objectPosition = grade.pos
   }

   const setBusy = (post, busy) => {
      post.refs.input.disabled = busy
      post.refs.send.disabled = busy
      post.refs.chips.forEach(chip => { chip.disabled = busy })
   }

   const addComment = (post, who, text, isBot = false) => {
      const item = document.createElement('li')
      if (isBot) item.classList.add('is-bot')

      const name = document.createElement('strong')
      name.textContent = who
      item.append(name, document.createTextNode(` ${text}`))
      post.refs.comments.append(item)
   }

   const applyEdits = (post, text) => {
      const labels = []

      if (JUMP.test(text)) {
         post.sourceIndex = (post.sourceIndex + 1) % state.album.sources.length
         const next = state.album.sources[post.sourceIndex]
         post.refs.media.classList.add('is-swapping')
         window.setTimeout(() => {
            post.refs.img.src = next.src
            post.refs.img.alt = next.alt
            post.refs.media.classList.remove('is-swapping')
            if (state.saved.includes(post)) renderWall()
         }, 260)
         labels.push('a different angle')
         return labels
      }

      EDIT_RULES.forEach(rule => {
         if (!rule.re.test(text)) return
         rule.apply(post.grade)
         labels.push(rule.label)
      })

      if (labels.length) applyMedia(post)
      return labels
   }

   const sendComment = (post, raw) => {
      const text = raw.trim()
      if (!text || post.busy) return

      post.busy = true
      post.refs.input.value = ''
      setBusy(post, true)
      addComment(post, 'you', text)
      post.refs.media.classList.add('is-working')

      window.setTimeout(() => {
         const labels = applyEdits(post, text)
         post.refs.media.classList.remove('is-working')
         post.refs.media.classList.add('is-reworked')
         window.setTimeout(() => post.refs.media.classList.remove('is-reworked'), 1000)

         if (state.saved.includes(post)) renderWall()

         const reply = labels.length
            ? `Reworked — ${labels.join(' and ')}. Same faces, new pass.`
            : 'Tell me what to change: “warmer”, “black and white”, “closer crop” or “another angle”.'
         addComment(post, 'plus one', reply, true)

         post.busy = false
         setBusy(post, false)
      }, 1500)
   }

   const toggleLike = post => {
      post.liked = !post.liked
      post.likes += post.liked ? 1 : -1
      post.refs.likeBtn.classList.toggle('is-on', post.liked)
      post.refs.likeBtn.setAttribute('aria-pressed', String(post.liked))
      post.refs.likeBtn.querySelector('i').className = post.liked ? 'ri-heart-3-fill' : 'ri-heart-3-line'
      post.refs.likes.textContent = post.likes
   }

   const toggleSave = post => {
      post.saved = !post.saved
      post.refs.saveBtn.classList.toggle('is-on', post.saved)
      post.refs.saveBtn.setAttribute('aria-pressed', String(post.saved))
      post.refs.saveBtn.querySelector('i').className = post.saved ? 'ri-bookmark-3-fill' : 'ri-bookmark-3-line'

      if (post.saved) state.saved.push(post)
      else state.saved = state.saved.filter(item => item !== post)

      updateSaveCounts()
      renderWall()
      showToast(post.saved ? 'Saved to your wall.' : 'Removed from your wall.')
   }

   const copyText = async text => {
      try {
         await navigator.clipboard.writeText(text)
         return true
      } catch {
         const area = document.createElement('textarea')
         area.value = text
         area.setAttribute('readonly', '')
         area.style.position = 'fixed'
         area.style.opacity = '0'
         document.body.append(area)
         area.select()
         let copied = false
         try {
            copied = document.execCommand('copy')
         } catch {
            copied = false
         }
         area.remove()
         return copied
      }
   }

   const sharePost = async post => {
      const url = `${location.href.split('#')[0]}#post-${post.index + 1}`
      const text = `${post.activity} — ${state.album.title}`

      if (navigator.share) {
         try {
            await navigator.share({ title: state.album.title, text, url })
            return
         } catch (error) {
            if (error && error.name === 'AbortError') return
         }
      }

      const copied = await copyText(url)
      showToast(copied ? 'Link copied — send it to the group chat.' : 'Copy the address bar link to share this frame.', 4200)
   }

   const downloadPost = async post => {
      const button = post.refs.downloadBtn
      if (button.disabled) return

      const icon = button.querySelector('i')
      button.disabled = true
      button.classList.add('is-busy')
      icon.className = 'ri-loader-4-line'

      const slug = (state.album.title || 'plus-one')
         .toLowerCase()
         .replace(/[^a-z0-9]+/g, '-')
         .replace(/^-+|-+$/g, '')
         .slice(0, 42) || 'plus-one'
      const filename = `${slug}-frame-${String(post.index + 1).padStart(3, '0')}.jpg`

      const result = await window.plusOneDownload.frame({
         src: post.refs.img.src,
         filename,
         filter: post.refs.img.style.filter || 'none',
         zoom: post.grade.z,
         pos: post.grade.pos
      })

      button.classList.remove('is-busy')
      button.classList.add('is-done')
      icon.className = result === 'failed' ? 'ri-error-warning-line' : 'ri-check-line'

      if (result === 'baked') showToast('Frame downloaded — your edits are baked in.', 3200)
      else if (result === 'source') showToast('Frame opened full-size in a new tab — save it from there.', 4000)
      else showToast('That frame could not be downloaded. Try again.', 3600)

      window.setTimeout(() => {
         button.classList.remove('is-done')
         icon.className = 'ri-download-2-line'
         button.disabled = false
      }, 1500)
   }

   const createPost = () => {
      const album = state.album
      const index = state.posts.length
      const activity = album.activities[index % album.activities.length]
      const sourceIndex = index % album.sources.length
      const source = album.sources[sourceIndex]
      const grade = { ...GRADES[index % GRADES.length] }

      const post = {
         index,
         activity,
         sourceIndex,
         grade,
         likes: 14 + (index * 7) % 41,
         liked: false,
         saved: false,
         busy: false
      }

      const el = document.createElement('article')
      el.className = 'post'
      el.id = `post-${index + 1}`
      el.style.animationDelay = `${(index % 3) * 70}ms`
      el.innerHTML = `
         <header class="post__head">
            <span class="post__avatar">${MARK}</span>
            <div class="post__who">
               <p class="post__name">plus one <span class="post__badge">ai photographer</span></p>
               <p class="post__place"><i class="ri-map-pin-2-line"></i>${esc(album.venue)}</p>
            </div>
            <time class="post__time">${esc(timeAgo(index))}</time>
         </header>

         <figure class="post__media">
            <img src="${esc(source.src)}" alt="${esc(source.alt)}" loading="lazy" decoding="async">
            <span class="post__frame">frame ${String(index + 1).padStart(3, '0')}</span>
            <figcaption class="post__stamp">${esc(frameTime(index))} · ${esc(activity)}</figcaption>
            <div class="post__working"><i aria-hidden="true"></i>Reworking this frame</div>
         </figure>

         <div class="post__bar">
            <button type="button" class="post__act" data-act="like" aria-pressed="false" aria-label="Like this frame">
               <i class="ri-heart-3-line"></i>
            </button>
            <button type="button" class="post__act" data-act="comment" aria-label="Comment on this frame">
               <i class="ri-chat-3-line"></i>
            </button>
            <button type="button" class="post__act" data-act="share" aria-label="Share this frame">
               <i class="ri-send-plane-line"></i>
            </button>
            <button type="button" class="post__act" data-act="download" aria-label="Download this frame">
               <i class="ri-download-2-line"></i>
            </button>
            <button type="button" class="post__act" data-act="save" aria-pressed="false" aria-label="Save to your wall">
               <i class="ri-bookmark-3-line"></i>
            </button>
         </div>

         <div class="post__copy">
            <p class="post__likes"><span data-likes>${post.likes}</span> likes</p>
            <p class="post__caption"><strong>plus one</strong> ${esc(activity)}. ${esc(briefFragment(index, activity))}</p>
            <p class="post__tags">#plusone #${esc(album.occasionKey)}</p>
            <ul class="post__comments">
               <li class="is-bot"><strong>plus one</strong> ${esc(OPENERS[index % OPENERS.length])}</li>
            </ul>
         </div>

         <div class="post__ask">
            <div class="post__chips">
               <button type="button" data-edit="warmer">Warmer</button>
               <button type="button" data-edit="black and white">B&amp;W</button>
               <button type="button" data-edit="closer crop">Closer crop</button>
               <button type="button" data-edit="another angle">Another angle</button>
            </div>
            <form class="post__composer">
               <input type="text" placeholder="Comment to rework this frame…" aria-label="Comment to rework this frame">
               <button type="submit" aria-label="Send comment"><i class="ri-arrow-up-line"></i></button>
            </form>
         </div>
      `

      post.refs = {
         img: el.querySelector('.post__media img'),
         media: el.querySelector('.post__media'),
         likes: el.querySelector('[data-likes]'),
         comments: el.querySelector('.post__comments'),
         input: el.querySelector('.post__composer input'),
         send: el.querySelector('.post__composer button'),
         chips: Array.from(el.querySelectorAll('[data-edit]')),
         likeBtn: el.querySelector('[data-act="like"]'),
         downloadBtn: el.querySelector('[data-act="download"]'),
         saveBtn: el.querySelector('[data-act="save"]')
      }

      applyMedia(post)

      post.refs.likeBtn.addEventListener('click', () => toggleLike(post))
      post.refs.saveBtn.addEventListener('click', () => toggleSave(post))
      post.refs.downloadBtn.addEventListener('click', () => downloadPost(post))
      el.querySelector('[data-act="share"]').addEventListener('click', () => sharePost(post))
      el.querySelector('[data-act="comment"]').addEventListener('click', () => {
         post.refs.input.focus({ preventScroll: true })
         el.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
      })

      post.refs.input.addEventListener('keydown', event => {
         if (event.key === 'Escape') post.refs.input.blur()
      })

      el.querySelector('.post__composer').addEventListener('submit', event => {
         event.preventDefault()
         sendComment(post, post.refs.input.value)
      })

      post.refs.chips.forEach(chip => {
         chip.addEventListener('click', () => sendComment(post, chip.dataset.edit))
      })

      state.posts.push(post)
      post.el = el
      return el
   }

   const updateFrames = () => {
      if (!state.album) return
      const count = state.posts.length
      feedFrames.textContent = `${count} frame${count === 1 ? '' : 's'} · still developing`
   }

   const ensureFeedFilled = () => {
      if (!state.album) return
      const rect = feedMore.getBoundingClientRect()
      if (rect.top < window.innerHeight + 800) appendBatch(3)
   }

   const appendBatch = count => {
      if (!state.album || state.generating) return
      state.generating = true
      const epoch = state.epoch

      window.setTimeout(() => {
         if (epoch !== state.epoch) return
         const fragment = document.createDocumentFragment()
         for (let i = 0; i < count; i += 1) fragment.append(createPost())
         feedEl.append(fragment)
         state.generating = false
         updateFrames()
         rememberAlbum()
         ensureFeedFilled()
      }, 240)
   }

   if ('IntersectionObserver' in window) {
      const sentinel = new IntersectionObserver(entries => {
         if (entries.some(entry => entry.isIntersecting)) appendBatch(3)
      }, { rootMargin: '700px 0px' })

      sentinel.observe(feedMore)
   } else {
      window.addEventListener('scroll', () => {
         if (window.innerHeight + window.scrollY > document.body.offsetHeight - 900) appendBatch(3)
      }, { passive: true })
   }

   /*=============== WALL ===============*/
   const wall = document.getElementById('wall')
   const wallGrid = document.getElementById('wall-grid')
   const wallCount = document.getElementById('wall-count')
   const openWallBtn = document.getElementById('open-wall')
   const closeWallBtn = document.getElementById('wall-close')
   const wallHint = document.getElementById('wall-hint')
   let wallReturnFocus = null

   const updateSaveCounts = () => {
      document.querySelectorAll('[data-save-count]').forEach(node => {
         node.textContent = state.saved.length
      })
      wallCount.textContent = state.saved.length
   }

   const renderWall = () => {
      wallGrid.innerHTML = ''

      if (!state.saved.length) {
         wallHint.hidden = false
         const empty = document.createElement('p')
         empty.className = 'wall__empty'
         empty.innerHTML = '<i class="ri-bookmark-3-line" aria-hidden="true"></i>Nothing saved yet. Bookmark a frame and it lands here, edits and all.'
         wallGrid.append(empty)
         return
      }

      wallHint.hidden = true
      state.saved
         .slice()
         .sort((a, b) => a.index - b.index)
         .forEach(post => {
            const thumb = document.createElement('button')
            thumb.type = 'button'
            thumb.className = 'wall__thumb'

            const img = document.createElement('img')
            img.src = post.refs.img.src
            img.alt = post.refs.img.alt
            img.style.filter = post.refs.img.style.filter
            img.style.transform = post.refs.img.style.transform
            img.style.objectPosition = post.refs.img.style.objectPosition

            const caption = document.createElement('span')
            caption.textContent = post.activity

            thumb.append(img, caption)
            thumb.addEventListener('click', () => {
               closeWall()
               window.setTimeout(() => {
                  post.el.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
                  post.el.classList.remove('is-spotlit')
                  void post.el.offsetWidth
                  post.el.classList.add('is-spotlit')
               }, 260)
            })

            wallGrid.append(thumb)
         })
   }

   const openWall = () => {
      wallReturnFocus = document.activeElement
      wall.classList.add('is-open')
      wall.setAttribute('aria-hidden', 'false')
      document.body.style.overflow = 'hidden'
      closeWallBtn.focus()
   }

   const closeWall = () => {
      if (!wall.classList.contains('is-open')) return
      wall.classList.remove('is-open')
      wall.setAttribute('aria-hidden', 'true')
      document.body.style.overflow = ''
      if (wallReturnFocus && typeof wallReturnFocus.focus === 'function') {
         wallReturnFocus.focus({ preventScroll: true })
      }
   }

   openWallBtn.addEventListener('click', openWall)
   closeWallBtn.addEventListener('click', closeWall)
   wall.querySelector('[data-wall-close]').addEventListener('click', closeWall)

   document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && wall.classList.contains('is-open')) closeWall()
   })

   /*=============== TOAST ===============*/
   const toast = document.getElementById('toast')
   let toastTimer

   function showToast(message, duration = 2400) {
      toast.textContent = message
      toast.classList.add('is-on')
      window.clearTimeout(toastTimer)
      toastTimer = window.setTimeout(() => toast.classList.remove('is-on'), duration)
   }

   /*=============== FIRST PAINT ===============*/
   renderWall()
   updateSaveCounts()

   // Keep the studio title in view on wide screens without a jarring jump
   window.addEventListener('load', () => {
      document.documentElement.classList.add('is-ready')
   })
})()
