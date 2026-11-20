# Lyle Okoth — projects

## SautiFlow — voice and podcast studio

Voice platform for local Kenyan languages: voice design with persona bibles and pronunciation lexicons, text-to-speech, voice cloning from consented reference audio, speech-to-text with diarisation, and AI-agent podcast production — research, script, casting, render, master and show notes behind human approval gates. FastAPI studio, account and voice libraries, credit-pack checkout and reproducible renders. Serves 2,100 monthly creators at 61% week-four retention.
Stack: FastAPI, PostgreSQL, PyTorch TTS, Docker, Render.
Link: https://www.sautiflow.co.ke/

## Suraya — photoreal Kenyan faces

Audit-driven latent diffusion model for photorealistic Kenyan faces, built as a small, inspectable experiment rather than a product.
Implementation: 889-image data audit, face detection and alignment, a compact 66M UNet trained on a frozen SD VAE, KID-led evaluation.
Stack: PyTorch, Diffusers, LoRA, face alignment.
Link: https://github.com/lyle-mlengineer/suraya

## Vocalis — AI voice design studio

Brief-to-voice studio: describe a voice, design and audition it, refine the brief, organize albums and synthesize narration with rate, volume and style controls. Provider-agnostic Breeze and Fish Audio adapters, a credit ledger and idempotent M-Pesa / Stripe settlement.
Stack: FastAPI, provider adapters, M-Pesa / Stripe, vanilla JS.
Links: https://github.com/lyle-mlengineer/vocalis · https://vocalis-rvcw.onrender.com

## EchoID — speaker-labelled transcription

Upload, diarise, review and export speaker-labelled transcripts with timestamps, reusable speaker profiles, search and filters. A pluggable transcription provider behind one JSON contract, credit billing with M-Pesa and Stripe.
Stack: FastAPI, ASR adapters, pyannote.audio, PostgreSQL.
Links: https://github.com/lyle-mlengineer/echoid · https://echoid.onrender.com

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

Private coding agent for Google Colab's free T4: Qwen2.5-Coder-7B runs locally at NF4, plans inside the repository, edits with a tree-sitter map and BM25 retrieval, verifies with Ruff and pytest, and commits every checkpoint to an isolated git branch. Published on PyPI as co-agent-coder 0.2.1 with no API keys or per-token cost.
Stack: Python, local inference, tree-sitter, BM25, git integration.
Links: https://github.com/lyle-mlengineer/coagent · https://pypi.org/project/co-agent-coder/

## Docent — AI product guide

Explore a site, build an evidence-backed model of its workflows, narrate a walkthrough and guide users live. Shipped the public front door: FastAPI, PostgreSQL and Jinja2 with a durable waitlist, contact inbox, protected admin, CSV export, rate limits and a strict CSP.
Stack: FastAPI, PostgreSQL, Jinja2, strict CSP.
Links: https://docent-9a62.onrender.com/ · https://github.com/lyle-mlengineer/docent

## SnapToSpot — website → campaign kit

Turns a website into a five-platform campaign kit — stills, video, poster and copy deck — built only from facts the site can support. The model writes the words and structure, a deterministic renderer sets the type, and every number traces to a source span. In active development.
Stack: FastAPI, PostgreSQL/pgvector, Alembic, OAuth2, deterministic renderer.
Link: https://github.com/lyle-mlengineer/Snap2Spot

## Skipper — the job-search agent

A private agent that takes a job posting and produces a grounded application pack: research, CV (PDF/DOCX), cover letter, email, spoken answers and interview briefs, with a status dashboard.
Stack: FastAPI, SQLAlchemy, SQLite FTS5, Groq (openai/gpt-oss), Jinja2, vanilla JS.
