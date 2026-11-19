# Lyle Okoth — projects

## SautiFlow — voice and podcast studio

FastAPI podcast and voice-over studio with voice libraries and credit-pack checkout. Turns a written script into dozens of voiced, mixed audio skits in a single session. Serves 2,100 monthly creators at 61% week-four retention.
Stack: FastAPI, PostgreSQL, PyTorch TTS, Docker, Render.
Link: https://www.sautiflow.co.ke/

## Suraya — photoreal Kenyan faces

Audit-driven latent diffusion model for photorealistic Kenyan faces, built as a small, inspectable experiment rather than a product.
Implementation: 889-image data audit, face detection and alignment, a compact 66M UNet trained on a frozen SD VAE, KID-led evaluation.
Stack: PyTorch, Diffusers, LoRA, face alignment.
Link: https://github.com/lyle-mlengineer/suraya

## Vocalis — AI voice design studio

Design, refine and synthesize narration with rate, style and volume controls. Provider-agnostic voice adapters with a credit ledger and idempotent settlement.
Stack: FastAPI, provider adapters, M-Pesa / Stripe, vanilla JS.
Link: https://lyle-mlengineer.github.io/portfolio-frontend/vocalis/

## EchoID — speaker-labelled transcription

Speaker-labelled transcription studio with search, review and export. Provider-agnostic transcription adapters, evaluation before release.
Stack: FastAPI, ASR adapters, pyannote.audio, PostgreSQL.
Link: https://lyle-mlengineer.github.io/portfolio-frontend/echoid/

## LabelSet — audio data sourcing and labelling

Audio-first data sourcing and labelling with review, KES billing and JSONL export. Built from the labelling bottleneck seen on every speech project.
Stack: FastAPI, PostgreSQL, JSONL export, review queues.
Link: https://labelset.onrender.com

## FaceForm — synthetic portraits

Photoreal synthetic portraits from a written casting brief, ready to license and reuse.
Stack: Stable Diffusion / SDXL, LoRA, DreamBooth.
Link: https://faceform-2rkf.onrender.com

## PlusOne — personal AI photographer

A photo story of your event, built from your people and a few reference photos.
Stack: diffusion pipelines, identity conditioning, FastAPI.
Link: https://pigamagic.onrender.com

## coAgent — private coding agent

A private coding agent for Google Colab's free T4: local inference, test-driven edits and git checkpoints. 0.2.1 on PyPI.
Stack: Python, local inference, git integration.
Link: https://coagent-web.onrender.com/

## SnapToSpot — website → campaign kit

Turns a website into a five-platform campaign kit built only from facts the site can support.
Stack: FastAPI, SQLite, deterministic renderer, LLM extraction.
Link: https://github.com/lyle-mlengineer/Snap2Spot

## Skipper — the job-search agent

A private agent that takes a job posting and produces a grounded application pack: research, CV (PDF/DOCX), cover letter, email, spoken answers and interview briefs, with a status dashboard.
Stack: FastAPI, SQLAlchemy, SQLite FTS5, Groq (openai/gpt-oss), Jinja2, vanilla JS.
