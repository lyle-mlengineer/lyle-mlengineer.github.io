# Instagram launch kit — Lyle Okoth portfolio

**Portfolio:** https://lyle-mlengineer.github.io
**Assets:** 4-image carousel (1080 × 1350) + 1 Reel (1080 × 1920, 18 s, silent)
**Link:** Instagram captions do not carry clickable links. The URL lives in the bio, and the Reel says "tap the link in bio".

---

## Carousel caption

```text
Most speech demos sound impressive for thirty seconds.

Then the audio gets noisy, the speaker switches from English to Sheng mid-sentence, and the transcript turns into guesswork.

That gap — between a demo and a product — is the work I do.

I'm a machine learning engineer at SautiFlow Labs in Nairobi. Six years of speech AI for African languages, and the portfolio is finally live:

→ SautiFlow — a script into fully voiced, mixed skits. 2,100 monthly creators.
→ Vocalis — brand voices trained from licensed audio, served as a streaming API.
→ EchoID — speaker-aware transcription: who spoke, what they said, when.
→ LabelSet, FaceForm, PigaMagic, coAgent and Docent — the rest of the build list.

The numbers behind them:

23.4% → 11.8% word error rate on Swahili and Sheng
1.4 s → 310 ms median first audio on live translation
42 concurrent voices per GPU, 58% lower inference cost
38,000 hours of audio processed a year, 68% less manual labelling

Anyone can demo a model. The work is making it survive noisy audio, code-switching and a listener who is waiting.

Full case studies are in the link in bio.

#SpeechAI #MachineLearning #SpeechRecognition #TextToSpeech #AfricanLanguages #NLP #MLOps #KenyaTech #Nairobi #AIEngineer
```

About 1,260 characters, comfortably inside the 2,200 limit. Instagram shows roughly the first 125 characters before "more", which is exactly the three opening lines above — so the hook is fully above the fold and the hashtags never affect it.

Hashtag note: Instagram's own guidance is that 3–5 topical tags outperform a wall of 30. The ten above are all relevant; if you prefer a cleaner caption, cut to the first five and put the rest in the first comment.

---

## Shorter caption (if you would rather lead with the numbers)

```text
Six years of speech AI, in four slides.

Swahili and Sheng ASR at 11.8% word error rate.
Live speech translation at 310 ms.
42 voices on one GPU.
2,100 monthly creators on a product I built end to end.

Built for the languages stock models handle worst — and measured in production, not in a notebook.

Case studies in the link in bio.

#SpeechAI #MachineLearning #AfricanLanguages #TextToSpeech #Nairobi
```

---

## Reel caption

```text
Speech AI that ships — not just a demo that works on one clean recording.

18 seconds through the work: Swahili and Sheng transcription at 11.8% WER, live speech-to-speech translation at 310 ms, 42 voices on a single GPU.

Captions are burned in. Sound off is fine.

Full case studies in the link in bio.

#SpeechAI #MachineLearning #SpeechRecognition #AfricanLanguages #KenyaTech #Nairobi
```

---

## Alt text

Instagram lets you add alt text per carousel slide. Open the post, tap the three dots, then "Edit alt text". Paste one of these for each slide in order.

**01-announcement.png**

```text
Dark card with pink accents reading "Speech AI that ships", a portrait of Lyle Okoth, and the figures 6+ years, 7 products and 310 ms median first audio.
```

**02-what-i-build.png**

```text
Card titled "One engineer. The whole stack." Four rows: automatic speech recognition at 11.8% WER, speech-to-speech translation at 310 ms, 42 voices per GPU, and 38,000 hours of audio processed a year, each with its tooling listed.
```

**03-selected-work.png**

```text
Four product screenshots — SautiFlow, Vocalis, EchoID and LabelSet — with one-line descriptions, three proof points (22-second skit render, 89% speaker accuracy, 68% less manual labelling) and the four projects still in progress.
```

**04-proof.png**

```text
Card titled "Proof, not promises" with four statistics: 7 shipped production projects, 310 ms first-audio latency, 42 voices per GPU and 2,100 monthly creators. A client quote, a contact band and a QR code to lyle-mlengineer.github.io.
```

**Reel cover**

```text
Closing frame of a silent motion graphic: a portrait of Lyle Okoth, the words "Lyle Okoth, Machine Learning Engineer, SautiFlow Labs" and the URL lyle-mlengineer.github.io.
```

---

## Posting checklist

1. **Carousel first.** Upload the four images in order as a single post. 4:5 is the tallest ratio Instagram allows in the feed, so it takes the most vertical space without being cropped.
2. Add the alt text to each slide before publishing.
3. Set the cover for the Reel manually — choose the closing frame with the portrait and URL, not the dark opening frame.
4. Post the Reel 24–48 hours later, and pin it to your profile grid so the profile shows motion above the fold.
5. Put the portfolio link in the bio and mention it in the caption once. Instagram does not make caption links clickable, so "link in bio" is not filler — it is the only path.
6. The four slides are also readable as a 1:1 crop in your profile grid: the headline sits in the top third of every card, so nothing important is lost.

---

## Files

| File | Use |
| --- | --- |
| `01-announcement.png` | Carousel slide 1 (1080 × 1350) |
| `02-what-i-build.png` | Carousel slide 2 (1080 × 1350) |
| `03-selected-work.png` | Carousel slide 3 (1080 × 1350) |
| `04-proof.png` | Carousel slide 4 (1080 × 1350) |
| `reel.mp4` | Reel, 1080 × 1920, 18 s, 30 fps, H.264 (1.2 MB) |
| `reel-poster.png` | Suggested Reel cover, 1080 × 1920 |
| `assets/cards.html` | Editable source for the four carousel slides |
| `assets/reel.html` | Editable, timeline-driven source for the Reel |
| `assets/capture-cards.mjs` | Re-renders the four slides |
| `assets/capture-reel.mjs` | Re-renders the Reel with headless Chrome + ffmpeg |
| `assets/capture-poster.mjs` | Re-renders the Reel cover at a chosen timestamp |
| `assets/preview-reel.mjs` | Renders single frames for checking (`node … 2.9 7.4 10.9 16.4`) |
| `assets/qr.png` | QR code used on slide 4 |

To edit copy, change the text in `assets/cards.html` or `assets/reel.html`, then run:

```text
node media/instagram/assets/capture-cards.mjs
node media/instagram/assets/capture-reel.mjs
node media/instagram/assets/capture-poster.mjs 17.4
```

The Reel keeps everything inside a 1080 × 1240 safe area — 260 px clear at the top for the camera/account row and 420 px clear at the bottom for the caption, audio and action buttons. Do not move text into those bands; it will be covered on the phone.
