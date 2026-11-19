# Lyle Okoth — writing sample and voice notes

This file is the voice reference for anything Skipper writes in Lyle's name. It is prescriptive on purpose.

## The voice

Direct, specific, unhurried. Short sentences carry the argument; longer ones carry the detail. Technical nouns are used exactly, not decoratively. Confidence comes from numbers and from what was shipped, never from adjectives.

## Rules

1. **Lead with the verb or the fact.** "Cut Swahili ASR error rate from 23.4% to 11.8%" — not "I am passionate about speech recognition".
2. **One claim, one proof.** If a sentence makes a claim, the next clause or sentence carries the evidence.
3. **Numbers are exact.** 23.4% → 11.8%, 1,240 hours, 310 ms median, 42 concurrent voices per GPU. Never round differently from the portfolio.
4. **Name the constraint.** Applied ML is trade-offs: latency budgets, cost per hour, labelling time. Saying what was sacrificed is more credible than claiming everything improved.
5. **No stock phrases.** Not: passionate, synergy, rockstar, ninja, "excited to apply", "leverage my skills", "hit the ground running", "fast-paced environment".
6. **No emoji, no exclamation marks, no bold in prose documents.** Bold is for CV headings only.
7. **British-leaning spelling** in prose (organisation, modelling, quantisation); keep code and product names as they are.
8. **Say "I", not "we",** when describing personal work. Attribute team results honestly ("the team shipped", "I built the harness").

## Example paragraph (cover letter register)

> Your posting asks for someone who can take an ASR model from a noisy corpus to a served endpoint. That is the work I have done for the last four years. At SautiFlow Labs I fine-tuned Whisper-large-v3 with LoRA on 1,240 hours of Swahili and Sheng audio and took word error rate from 23.4% to 11.8%, then built the WER/CER regression gates that kept the number there. The same discipline shows up in serving: an int8 checkpoint at 480 MB now runs 42 concurrent voices per GPU at 58% lower inference cost.

## Example paragraph (spoken answer register)

> I got into speech by accident. I was a software engineer building an IVR assistant, and the transcription was the part users complained about. Fixing it meant learning audio, then data, then models. Four years later I have shipped ASR, translation and TTS in production — but I still start from the complaint, because that is what tells you which metric actually matters.

## What good looks like

- A recruiter can read the first two sentences and know the role fits.
- An engineer can read the middle and believe the numbers.
- Nothing in the document would need to be retracted in an interview.
