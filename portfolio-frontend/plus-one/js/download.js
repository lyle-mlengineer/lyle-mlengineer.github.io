/*=============== FRAME DOWNLOAD ===============*/
(() => {
   'use strict'

   const safeSource = src => /^(blob:|data:)/.test(src)

   const loadSource = async src => {
      if (safeSource(src)) return { src, revoke: false }
      try {
         const response = await fetch(src, { mode: 'cors' })
         if (!response.ok) throw new Error('fetch failed')
         const blob = await response.blob()
         return { src: URL.createObjectURL(blob), revoke: true }
      } catch {
         return { src, revoke: false }
      }
   }

   const decode = src => new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = () => reject(new Error('decode failed'))
      img.src = src
   })

   const saveBlob = (blob, filename) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.append(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 4000)
   }

   const saveSource = (src, filename) => {
      const link = document.createElement('a')
      link.href = src
      link.download = filename
      // Local files count as cross-origin, so `download` is ignored and Chrome
      // would replace the page with the photo. Open it beside the app instead.
      if (window.location.protocol === 'file:') {
         link.target = '_blank'
         link.rel = 'noopener'
      }
      document.body.append(link)
      link.click()
      link.remove()
   }

   const frame = async ({
      src,
      filename = 'plus-one-frame.jpg',
      filter = 'none',
      zoom = 1,
      pos = '50% 50%',
      width = 1080,
      height = 1350
   }) => {
      if (!src) return 'failed'
      const loaded = await loadSource(src)

      try {
         const img = await decode(loaded.src)
         const canvas = document.createElement('canvas')
         canvas.width = width
         canvas.height = height
         const ctx = canvas.getContext('2d')
         if (!ctx) throw new Error('canvas unavailable')

         const scale = Math.max(width / img.naturalWidth, height / img.naturalHeight) * zoom
         const drawWidth = img.naturalWidth * scale
         const drawHeight = img.naturalHeight * scale
         const [px = 50, py = 50] = String(pos).trim().split(/\s+/).map(value => parseFloat(value) || 0)
         const x = (width - drawWidth) * (px / 100)
         const y = (height - drawHeight) * (py / 100)

         if ('filter' in ctx) ctx.filter = filter || 'none'
         ctx.drawImage(img, x, y, drawWidth, drawHeight)

         const blob = await new Promise((resolve, reject) => {
            canvas.toBlob(result => result ? resolve(result) : reject(new Error('encode failed')), 'image/jpeg', 0.92)
         })

         saveBlob(blob, filename)
         return 'baked'
      } catch {
         try {
            saveSource(src, filename)
            return 'source'
         } catch {
            return 'failed'
         }
      } finally {
         if (loaded.revoke) URL.revokeObjectURL(loaded.src)
      }
   }

   window.plusOneDownload = { frame }
})()
