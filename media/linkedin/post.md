# LinkedIn launch kit — Lyle Okoth portfolio

**Portfolio:** https://lyle-mlengineer.github.io
**Assets:** 4 square images (1200 × 1200) + 1 square video (1080 × 1080, 15 s, silent)

---

## Recommended title / opening line

> Six years of speech AI, in one place — my portfolio is live.

Alternatives:

- Speech AI that ships. My portfolio is live.
- From 23.4% WER to 310 ms: the work behind the portfolio.
- I build speech AI for the languages stock models handle worst. Here's the portfolio.

The first two lines are what people see before "…see more", so keep the link out of them.

---

## Post copy

```text
Most speech demos sound impressive for thirty seconds. Then the audio gets noisy, the speaker switches from English to Sheng, and the model falls apart.

My new portfolio is about the unglamorous part: making speech AI hold up in production.

I'm a machine learning engineer at SautiFlow Labs in Nairobi. Over six years I've moved from building web products, to building the data pipelines behind speech models, to training and shipping the models themselves.

What's in it:

→ SautiFlow — a script into fully voiced, mixed skits. 2,100 monthly creators.
→ Vocalis — brand voices trained from licensed audio, served as a streaming API.
→ EchoID — speaker-aware transcription: who spoke, what they said, when.
→ LabelSet, FaceForm, PigaMagic, coAgent and Docent — the rest of the build list.

The numbers I care about:

• Swahili and Sheng ASR: 23.4% → 11.8% word error rate
• Live speech-to-speech translation: 310 ms median first audio (p95 780 ms)
• Text-to-speech: 42 concurrent voices per GPU, inference cost down 58%
• Audio data: 38,000 hours processed a year, 68% less manual labelling

Anyone can demo a model. The work is making it survive noisy audio, code-switching and a listener who is waiting.

If you're building voice products for African languages — or trying to get a speech model out of a notebook and into production — I'd like to hear what you're working on.

Portfolio: https://lyle-mlengineer.github.io

#MachineLearning #SpeechAI #SpeechRecognition #TextToSpeech #AfricanLanguages #MLOps #Nairobi
```

(~1,650 characters — well inside LinkedIn's 3,000 limit.)

---

## Alt text for the images

**01-announcement.png**
Dark card with pink accents reading "Speech AI that ships", a portrait of Lyle Okoth, and the figures 6+ years, 7 products and 310 ms median first audio. Footer: lyle-mlengineer.github.io.

**02-what-i-build.png**
Card titled "One engineer. The whole speech stack." listing four capabilities: automatic speech recognition at 11.8% WER, speech-to-speech translation at 310 ms, 42 voices per GPU, and 38,000 hours of audio processed a year.

**03-selected-work.png**
Four product screenshots — SautiFlow, Vocalis, EchoID and LabelSet — with short descriptions, plus three proof points: a 22-second skit render, 89% speaker accuracy and 68% less manual labelling.

**04-proof.png**
Card titled "Proof, not promises" with four statistics: 7 shipped production projects, 310 ms first-audio latency, 42 voices per GPU and 2,100 monthly creators. Includes a client quote, a QR code and the portfolio URL.

---

## Suggested posting order

1. Upload the four images in order as a photo post, or upload **launch-video.mp4** on its own for more reach.
2. Paste the post copy above.
3. Add the alt text to each image in LinkedIn's "Add alt text" field.
4. Pin a first comment with the project you are proudest of, or tag a collaborator.

If you post the video instead of the images, use this shorter caption:

```text
Speech AI that ships — not just a demo that works on one clean recording.

My portfolio is live: six years of ASR, speech-to-speech translation and text-to-speech for African languages, with the numbers to show for it.

Transcript on screen. Sound off is fine.

https://lyle-mlengineer.github.io
```

---

## If you publish it as a LinkedIn Article

**Title:** Speech AI that ships: six years of turning models into products

```text
Most speech demos sound impressive for thirty seconds.

Then the audio gets noisy. The speaker switches from English to Sheng mid-sentence. Someone in the room laughs, and the transcript turns into guesswork. This is the part of speech AI that rarely makes a demo video, and it is the part I have spent six years working on.

I am a machine learning engineer at SautiFlow Labs in Nairobi. I build transcription, speech-to-speech translation and text-to-speech for African languages — starting with the data pipeline, then the model, then the API that has to stay fast under load.

Today my portfolio is live. It collects the work and, more importantly, the measurements behind it.

On Swahili and Sheng ASR, fine-tuning Whisper-large-v3 on 1,240 hours of in-house audio took word error rate from 23.4% to 11.8%. A streaming translation pipeline went from a 1.4-second batch baseline to 310 ms median first audio on a single T4 GPU. A 1.6 GB TTS checkpoint compressed to 480 MB, which put 42 concurrent voices on one GPU and cut inference cost by 58%.

Those numbers are not the point on their own. The point is what they make possible: a creator producing forty skits in a session instead of four, a support team searching 40,000 hours of archived calls, a learner hearing a lesson in the language they think in.

The portfolio includes the shipped products (SautiFlow, Vocalis, EchoID, LabelSet), the builds in progress (coAgent, Docent) and the case studies behind each number.

If you are working on voice for African languages, or trying to move a speech model from a notebook into production, my inbox is open.

https://lyle-mlengineer.github.io
```

---

## Files

| File | Use |
| --- | --- |
| `01-announcement.png` | Main announcement image (1200 × 1200) |
| `02-what-i-build.png` | Capability overview (1200 × 1200) |
| `03-selected-work.png` | Project screenshots (1200 × 1200) |
| `04-proof.png` | Metrics, quote, QR code (1200 × 1200) |
| `launch-video.mp4` | 15-second silent loop, 30 fps, H.264 (1.1 MB) |
| `video-poster.png` | Thumbnail / poster frame for the video (1080 × 1080) |
| `assets/cards.html` | Editable source for the four stills |
| `assets/video.html` | Editable, timeline-driven source for the video |
| `assets/capture-cards.mjs` | Re-renders the four PNGs with headless Chrome |
| `assets/capture-video.mjs` | Re-renders the video with headless Chrome + ffmpeg |
| `assets/qr.png` | QR code used on card 04 |

To edit copy, change the text in `assets/cards.html` or `assets/video.html`, then run:

```text
node media/linkedin/assets/capture-cards.mjs
node media/linkedin/assets/capture-video.mjs
```

The video has no audio track and all text is burned in, so it works with sound off. LinkedIn recommends a 1:1 or 4:5 frame for feed video; 1:1 is used here to match the images. When you upload it, set `video-poster.png` as the thumbnail so the feed shows the portrait and URL instead of the dark opening frame.
