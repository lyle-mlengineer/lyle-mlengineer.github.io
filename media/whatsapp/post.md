# WhatsApp launch kit — Lyle Okoth portfolio

**Portfolio:** https://lyle-mlengineer.github.io
**Assets:** 1 status image (1080 × 1920), 1 share card (1080 × 1080), 1 status video (1080 × 1920, 18 s, silent)
**Tone:** WhatsApp is a personal channel. No hashtags, no marketing voice, no "excited to announce". Write like you are sending it to one person.

---

## Status

Post **status.png** (or **status-video.mp4** if you want motion) with this caption:

```text
Six years of speech AI, now in one place. Transcription, live translation and synthetic voices for African languages — with the numbers behind them.
lyle-mlengineer.github.io
```

Shorter option, if the caption covers the image:

```text
Portfolio is live. Speech AI that ships.
```

Status notes:

- Text is already burned into both the image and the video, so they work even with the caption hidden.
- The image keeps 300 px clear at the bottom for WhatsApp's reply bar and "swipe up" area.
- If you post the video, it loops cleanly and needs no sound. WhatsApp autoplays it muted.
- Status allows one caption line before "Read more"; keep the URL on the second line so it still shows after the truncation.

---

## Message to an individual

Use this for recruiters, founders, and people you have actually spoken to. Send it as one message, not five.

```text
Hi [Name] — I've finally put my portfolio together and thought of you.

I'm a machine learning engineer at SautiFlow Labs in Nairobi. Six years of speech work: Swahili and Sheng ASR at 11.8% word error rate, live speech-to-speech translation at 310 ms, and 42 voices running on a single GPU.

The site has the case studies and the numbers behind each one:
https://lyle-mlengineer.github.io

Would genuinely value your take — especially on [specific thing they work on].
```

Replace the bracketed parts. The last line is the reason they should reply; without it this is a broadcast, not a message.

---

## Group message

Post **share.png** first, then this as the caption. Works for alumni groups, ML communities, Nairobi tech groups.

```text
Sharing my portfolio in case it's useful to anyone here.

Speech AI for African languages — ASR, speech-to-speech translation and TTS — with the measurements behind each project: 23.4% → 11.8% WER, 1.4 s → 310 ms first audio, 42 voices per GPU.

Eight projects, four shipped products and two in development.
https://lyle-mlengineer.github.io

Happy to answer questions on any of it.
```

Do not send this to groups you have not posted in before. In most Kenyan tech and alumni groups, a link from a stranger reads as spam.

---

## Broadcast list

Only if people opted in. Broadcast messages are one-to-many and replies come back privately, so the copy has to work without context.

```text
Lyle Okoth — portfolio, 2026

Machine learning engineer, SautiFlow Labs, Nairobi. Six years building speech AI for African languages.

What's in it:
• SautiFlow — script to voiced skit, 2,100 monthly creators
• Vocalis — brand voices as a streaming API
• EchoID — who spoke, when, and what
• ASR at 11.8% WER, live translation at 310 ms, 42 voices per GPU

https://lyle-mlengineer.github.io
lyleokoth.mlengineer@gmail.com · +254 797 668 066
```

---

## Follow-up (48 hours later, only if they replied or reacted)

```text
Thanks for taking a look — if any of the speech work overlaps with what you're building, I'd be glad to walk you through it. The EchoID and SautiFlow case studies are the two with the most detail.
```

---

## Formatting that works in WhatsApp

- `*bold*` with single asterisks, `_italic_` with underscores. Do not use Markdown `**double asterisks**` — WhatsApp shows them literally.
- Long messages get collapsed behind "Read more". Put the first two lines to work.
- WhatsApp does not render link previews from your own portfolio unless the page has Open Graph tags. Check that `index.html` has `og:title`, `og:description` and `og:image` set, otherwise the link appears as bare text.
- Send to yourself first to see how the compression treats the share card. Text under 30 px can blur after WhatsApp's recompression — the QR is sized at 104 px so it survives, but scan it once from a phone before sending it to a group.

---

## Files

| File | Use |
| --- | --- |
| `status.png` | Status image, 1080 × 1920 |
| `status-video.mp4` | Status video, 1080 × 1920, 18 s, 30 fps, H.264 (1.2 MB) |
| `share.png` | Forwardable square card, 1080 × 1080, with QR and contact details |
| `assets/status.html` | Editable source for the status image |
| `assets/share.html` | Editable source for the share card |
| `assets/status-video.html` | Editable, timeline-driven source for the status video |
| `assets/capture-cards.mjs` | Re-renders `status.png` and `share.png` |
| `assets/capture-video.mjs` | Re-renders `status-video.mp4` with headless Chrome + ffmpeg |
| `assets/qr.png` | QR code used on the share card |

To edit copy, change the text in the HTML files, then run:

```text
node media/whatsapp/assets/capture-cards.mjs
node media/whatsapp/assets/capture-video.mjs
```

The video is the same 18-second edit as the Instagram Reel with one change: the closing line says "reply to this status · +254 797 668 066" instead of "tap the link in bio", because WhatsApp has no bio link.

---

## Order to send

1. Update your WhatsApp profile photo or About line to point at the portfolio (`Speech AI · lyle-mlengineer.github.io`).
2. Post the status in the evening, around 19:00–21:00 EAT, when status views peak.
3. Send the individual message to 5–10 people you have actually worked with — not a bulk list.
4. Post the share card in one or two relevant groups the next morning.
5. Only use the broadcast list if people opted in. Otherwise skip it.
