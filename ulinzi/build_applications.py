"""Build the ULINZI PRO application package: two tailored resumes and cover letters.

Targets the two talent areas on https://ulinzipro.com/careers:
  * AI & Machine Learning (specialization value: ai-ml)
  * Software Development / Full-stack (specialization value: software-dev)

The careers page currently shows "Not Currently Hiring" and asks candidates to
send a CV, portfolio and detailed cover letter to careers@ulinzipro.com, and/or
register interest through the on-page form. Both packages follow that process.

Run from the repository root:
    /tmp/opencode/cv-venv/bin/python ulinzi/build_applications.py
Then convert the DOCX files to PDF with LibreOffice.
"""
from pathlib import Path
import sys

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent
CV_DIR = ROOT.parent / "cv"
sys.path.insert(0, str(CV_DIR))

import _generate_cvs as base  # noqa: E402

base.LOCATION = "Nairobi, Kenya · Remote (UTC+3)"
COMPANY = "ULINZI PRO"
COMPANY_LINE = "ULINZI PRO · Talent Team"
COMPANY_ADDRESS = "Kerugoya, Kirinyaga County, Kenya · careers@ulinzipro.com"
DATE = "17 November 2026"

PROJECT_FACEFORM = base.PROJECT_FACEFORM
PROJECT_SNAPSPOT = base.PROJECT_SNAP
PROJECT_PLUSONE = base.PROJECT_PLUSONE


# ---------------------------------------------------------------------------
# 1. AI / ML resume
# ---------------------------------------------------------------------------
AI_ML = {
    "file": str(ROOT / "LYLE-OKOTH-ULINZI-AI-ML-RESUME.docx"),
    "headline": "AI/ML ENGINEER | COMPUTER VISION, SPEECH & EDGE INFERENCE",
    "summary": (
        "AI/ML Engineer with four years of experience taking vision and speech models from dataset audit to "
        "production inference, including on-premise and single-GPU hardware. Designed Suraya, an audit-driven "
        "diffusion study for Kenyan faces with a VAE quality gate and KID-led evaluation; shipped streaming "
        "speech-to-speech translation at 310 ms median first-audio latency on one T4; and cut Swahili and Sheng ASR "
        "word error rate from 23.4% to 11.8%. Studying computer security and forensics, with a mechatronics "
        "background that makes hardware-adjacent work natural."
    ),
    "competencies": [
        ("Computer Vision & Generative Models", "Face detection and alignment, latent diffusion, Stable Diffusion / "
                                                 "SDXL and LoRA, VAE quality gates, KID / FID and blind review, "
                                                 "synthetic-data generation, content provenance"),
        ("Speech & Language", "ASR (Whisper, wav2vec 2.0, NVIDIA NeMo), speaker diarisation and embeddings, TTS and "
                              "voice design (VITS, XTTS-v2), multilingual Swahili and Sheng models, streaming audio"),
        ("Training & Evaluation", "PyTorch, Hugging Face Transformers and Diffusers, LoRA / QLoRA, distributed "
                                  "training (DDP / FSDP), WER / CER / MOS, error analysis, Weights & Biases, MLflow, "
                                  "Optuna, DVC"),
        ("Edge & Production ML", "ONNX Runtime, TensorRT, Triton Inference Server, vLLM, int8 / FP16 / NF4 "
                                 "quantisation, KV caching, batching, p50/p95 latency and cost tuning, Docker, "
                                 "Kubernetes, on-prem and cloud GPUs"),
    ],
    "tech": [
        ("Languages", "Python, C++, SQL, JavaScript/TypeScript"),
        ("Vision & Speech", "PyTorch, Hugging Face Transformers, Diffusers, face detection and alignment, Whisper, "
                            "wav2vec 2.0, NVIDIA NeMo, pyannote.audio, Coqui TTS, torchaudio, librosa, FFmpeg"),
        ("Serving & Optimisation", "ONNX Runtime, TensorRT, Triton, vLLM, int8 / FP16 / NF4, KV caching, continuous "
                                   "batching, latency and throughput profiling"),
        ("Platform", "FastAPI, Docker, Kubernetes, Redis, Celery, PostgreSQL, AWS, GCP, Render, GitHub Actions"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Designed Suraya, a diffusion study for photoreal 256×256 Kenyan faces: an 889-image audit that set "
                 "resolution, crop and augmentation policy, face detect and align, a compact 66M UNet on a frozen SD "
                 "VAE, a paired SDXL LoRA track, a VAE quality gate and KID-led comparison."),
                ("Built FaceForm, a brief-to-portrait studio on NVIDIA Flux: prompt controls for age, ethnicity, "
                 "features and styling, gallery and album management, regenerate and refine, and per-image credits "
                 "with idempotent M-Pesa and Stripe settlement."),
                ("Built EchoID, a speaker-aware transcription studio: diarisation with speaker labels and timestamps, "
                 "reusable speaker profiles, search and filters, JSON, TXT and PDF export, and a pluggable ASR "
                 "provider behind one contract."),
                ("Built LabelSet, an audio data platform covering 11 speech task types including diarisation and voice "
                 "design, with 16 kHz preprocessing, a review workflow and JSONL dataset export."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 curated hours, comparing held-out and noisy field sets before promoting a checkpoint."),
                ("Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs on a single T4, down from a 1.4 s batch baseline."),
                ("Compressed a 1.6 GB TTS checkpoint to 480 MB with int8 quantisation and KV caching: 42 concurrent "
                 "voices per GPU, 3.1x throughput and 58% lower inference cost."),
                ("Built the evaluation harness — WER, CER, MOS and CI regression gates — which blocked 9 model "
                 "regressions from release in two quarters."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Designed batch and streaming pipelines (Airflow, Kafka, Spark) processing 6 TB / 38,000 hours of raw "
                 "audio a year into training-ready datasets."),
                ("Automated alignment and diarisation pre-labelling, cutting human labelling from 11 to 3.5 minutes per "
                 "audio hour; introduced DVC versioning so every release traces to an exact data snapshot."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Built REST and WebSocket APIs in Django and Node.js handling 1.2M requests a day at p95 latency "
                 "under 140 ms, with PostgreSQL, Redis and Twilio integrations."),
                ("Introduced Docker deploys and GitHub Actions CI/CD, moving releases from monthly to weekly, and "
                 "instrumented the telemetry later used to evaluate model and product changes."),
            ],
        },
    ],
    "projects": [base.PROJECT_SURAYA, base.PROJECT_ECHOID, PROJECT_FACEFORM],
    "education": base.EDUCATION,
    "certs": base.CERTS,
    "extra": None,
    "references": False,
    "compact": True,
}


# ---------------------------------------------------------------------------
# 2. Full-stack resume
# ---------------------------------------------------------------------------
FULLSTACK = {
    "file": str(ROOT / "LYLE-OKOTH-ULINZI-FULLSTACK-RESUME.docx"),
    "headline": "FULL-STACK DEVELOPER | PYTHON, REACT & SECURE MULTI-TENANT PLATFORMS",
    "summary": (
        "Full-Stack Developer with four years of experience shipping secure, multi-tenant web products end to end — "
        "React and server-rendered front ends, FastAPI, Django and Node.js APIs, PostgreSQL data models and Docker "
        "deployments. Built REST and WebSocket services handling 1.2M requests a day at p95 latency under 140 ms, "
        "credit-based billing with idempotent M-Pesa and Stripe settlement, and OAuth2, CSP and rate limiting into "
        "each product's defaults. Studying computer security and forensics, so security review is part of the build "
        "rather than a later step."
    ),
    "competencies": [
        ("Frontend & Product", "React and Next.js interfaces, server-rendered Jinja2 pages, responsive dashboards and "
                               "studios, UI/UX design, accessibility, Figma-to-code, documentation and handover"),
        ("Backend & APIs", "FastAPI, Django, Flask and Node.js services, REST and WebSocket APIs, OAuth2 / PKCE and "
                           "JWT, Pydantic contracts, SQLAlchemy and Alembic, background jobs, multi-tenant isolation"),
        ("Data & Payments", "PostgreSQL, SQLite, Redis and Elasticsearch, Celery workers, M-Pesa Daraja and Stripe, "
                            "idempotent settlement, signed webhooks, credit ledgers, CSV and JSONL exports"),
        ("Security & Delivery", "Content-Security-Policy, rate limiting, honeypots, secret redaction, least-privilege "
                                "access, Docker, Kubernetes, GitHub Actions CI/CD, Render, AWS and GCP, logging, "
                                "tracing and cost monitoring"),
    ],
    "tech": [
        ("Languages", "Python, JavaScript/TypeScript, SQL, C++"),
        ("Frontend", "React, Next.js, Jinja2, HTML, CSS, vanilla JavaScript, responsive layout"),
        ("Backend & Data", "FastAPI, Django, Flask, Node.js, PostgreSQL, SQLite, Redis, Elasticsearch, Celery, "
                           "Alembic"),
        ("Payments & Integrations", "M-Pesa Daraja, Stripe, Twilio voice and SMS, OAuth2 / PKCE, WebSocket "
                                    "streaming, NVIDIA Flux, Hugging Face"),
        ("DevOps & Cloud", "Docker, Kubernetes, GitHub Actions, Render, AWS, GCP, Linux, Git"),
    ],
    "jobs": [
        {
            "title": "Freelance Full-Stack Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Built SnapToSpot, a multi-tenant FastAPI service (OAuth2, Alembic, PostgreSQL/pgvector) where a "
                 "signed-in user submits a URL and gets a reviewed campaign kit: tenant-scoped data, a background "
                 "pipeline, and deterministic rendering that only uses facts traceable to a source span."),
                ("Built PlusOne's product shell — studio, photo feed, albums and a credit ledger — plus the rendering "
                 "agent behind it, with content-addressed dedupe, budget guards and partial-run recovery that returns "
                 "completed work and refunds instead of losing both."),
                ("Built EchoID's review workflow: speaker-labelled transcripts with timestamps, renaming, per-line "
                 "edits, search and filters, audio playback alongside text, and JSON, TXT or branded PDF export."),
                ("Shipped Docent's public front door — FastAPI, PostgreSQL and Jinja2 — with a durable waitlist, "
                 "contact inbox, protected admin surface, CSV export, rate limits and a strict CSP."),
            ],
        },
        {
            "title": "Machine Learning Engineer (full-stack responsibilities)",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Designed and shipped web interfaces for real-time streaming translation, transcription and "
                 "synthesis; SautiFlow now serves 2,100 monthly creators at 61% week-four retention."),
                ("Deployed model services on FastAPI, Triton and Kubernetes serving streaming speech at 310 ms median "
                 "first-audio latency, with logging and tracing for token usage and model drift."),
                ("Built authentication and authorisation controls that blocked bot API misuse without adding friction "
                 "for real users, and wrote the guardrail specs now used across model endpoints."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Built a synchronous and asynchronous backend for real-time and batch processing of user requests, "
                 "plus the data studio for human + AI collaborative collection and annotation."),
                ("Designed pipelines (Airflow, Kafka, Spark) processing 6 TB of audio a year and wrote the onboarding "
                 "documentation that new hires still use."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ monthly users, "
                 "from requirement framing with non-technical clients through design, build and iteration."),
                ("Built REST and WebSocket APIs in Django and Node.js handling 1.2M requests a day at p95 latency under "
                 "140 ms, and introduced Docker deployments with GitHub Actions CI/CD."),
                ("Took front-end test coverage from 0 to 71%, reported production bugs fell 34%, and trained the team's "
                 "first model — a scikit-learn intent classifier that deflected 28% of support chats."),
            ],
        },
    ],
    "projects": [PROJECT_SNAPSPOT, PROJECT_PLUSONE, base.PROJECT_ECHOID],
    "education": base.EDUCATION,
    "certs": base.CERTS,
    "extra": None,
    "references": False,
    "compact": True,
}


# ---------------------------------------------------------------------------
# Cover letters
# ---------------------------------------------------------------------------
def build_letter(path, subject, paragraphs, signoff):
    doc = base.build_doc()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(base.NAME)
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = base.DARK

    base.para(
        doc,
        f"{base.LOCATION}  |  {base.PHONE}  |  {base.EMAIL}",
        size=10,
        space_after=1,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )

    links = doc.add_paragraph()
    links.alignment = WD_ALIGN_PARAGRAPH.CENTER
    links.paragraph_format.space_after = Pt(12)
    for i, (label, url) in enumerate(base.LINKS):
        if i:
            sep = links.add_run("  |  ")
            sep.font.size = Pt(9)
        base.add_hyperlink(links, url, label, size=9)

    base.para(doc, DATE, size=10, space_after=10)
    base.para(doc, COMPANY_LINE, bold=True, size=10, space_after=2)
    base.para(doc, COMPANY_ADDRESS, size=10, space_after=10)
    base.para(doc, f"Re: {subject}", bold=True, size=10, space_after=10)
    base.para(doc, "Dear ULINZI PRO Talent Team,", size=10, space_after=8)

    for text in paragraphs:
        base.para(doc, text, size=10, space_after=7)

    base.para(doc, "Sincerely,", size=10, space_after=14)
    base.para(doc, base.NAME, bold=True, size=10, space_after=2)
    base.para(doc, signoff, size=10, space_after=0)

    doc.save(str(path))
    print("saved", path)


AI_ML_LETTER = [
    (
        "I am writing to register my interest in AI and machine learning work at ULINZI PRO. Your careers page "
        "describes a business built on AI-assisted surveillance, a security operations platform, drones and "
        "specialist hardware, and the engineers that work needs are the ones who can carry a model from a dataset "
        "audit to a low-latency process on whatever hardware is actually on site. That is the work I do."
    ),
    (
        "Most of my four years have gone into the unglamorous half of applied ML: deciding what data is good enough "
        "to train on, measuring a model honestly, then making it fast enough to run on one GPU. For Suraya, a "
        "diffusion model for Kenyan faces, I ran an 889-image audit that set resolution, cropping and augmentation "
        "policy, built face detect and align preprocessing, and paired a compact 66M-parameter UNet with an SDXL LoRA "
        "baseline so that the comparison, not just the model, is the deliverable. A VAE quality gate rejects "
        "recompression artefacts before sampling, and evaluation is KID-led rather than eyeballed."
    ),
    (
        "On the speech side I cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% with a LoRA fine-tune of "
        "Whisper-large-v3 on 1,240 curated hours, and shipped streaming speech-to-speech translation at 310 ms median "
        "first-audio latency on a single T4, down from a 1.4 s batch baseline. I also compressed a 1.6 GB TTS "
        "checkpoint to 480 MB with int8 quantisation and KV caching, which took capacity to 42 concurrent voices per "
        "GPU."
    ),
    (
        "That is the constraint that matters in your deployments. Surveillance and command-centre work rarely gets a "
        "rack of A100s; it gets an NVR, an edge box, or one GPU shared across many streams. I work in ONNX Runtime, "
        "TensorRT and Triton, tune int8 and FP16 paths against p50/p95 latency and cost rather than benchmark "
        "averages, and ship with Docker and Kubernetes. Swahili and Sheng models matter too when both the operators "
        "and the public are Kenyan."
    ),
    (
        "I am also studying computer security and forensics and hold a mechatronics diploma, so cameras, drones and "
        "access-control hardware are familiar ground rather than a translation exercise. Guardrails, PII redaction "
        "and consent paths are part of how I build, which is the right instinct in a security product."
    ),
    (
        "My work is at github.com/lyle-mlengineer, with three open speech datasets and two fine-tuned models on "
        "Hugging Face and write-ups for each project on my site. I am in Nairobi (UTC+3), happy to work remotely with "
        "overlap for Kerugoya, and would welcome a technical conversation about what your AI roadmap needs next."
    ),
]

FULLSTACK_LETTER = [
    (
        "I am writing to register my interest in software development roles at ULINZI PRO. Your product line runs "
        "from a security operations platform and video management software to access control, election monitoring "
        "and police tooling — the kind of systems where the interface has to be clear under pressure, the data has to "
        "stay with the right tenant, and a failed payment or a dropped WebSocket is not an acceptable outcome. That "
        "is the software I have spent four years shipping."
    ),
    (
        "I build end to end: requirement framing with non-technical stakeholders, React and server-rendered "
        "interfaces, FastAPI, Django or Node.js services, PostgreSQL models, and the deployment that keeps it "
        "running. For SnapToSpot I built a multi-tenant FastAPI service with OAuth2, Alembic migrations and "
        "pgvector retrieval, where a signed-in user submits a URL and gets a reviewed campaign kit produced by a "
        "background pipeline. For PlusOne I built the studio, photo feed and albums behind a credit ledger, plus the "
        "agent pipeline with content-addressed dedupe and budget guards, so a partial run returns completed work "
        "instead of losing it."
    ),
    (
        "Billing and access control are where I have done the most careful work. Vocalis, EchoID and FaceForm all run "
        "on credit ledgers with idempotent M-Pesa and Stripe settlement, signed webhooks and provider-confirmed "
        "top-ups, alongside authentication and authorisation that blocked bot API misuse without adding friction for "
        "real users. I default to a strict Content-Security-Policy, rate limits, honeypots and secret redaction, "
        "because in a security company those defaults are the product."
    ),
    (
        "Before freelancing I shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ "
        "monthly users, and built REST and WebSocket APIs in Django and Node.js handling 1.2M requests a day at p95 "
        "latency under 140 ms. I introduced Docker deploys and GitHub Actions CI/CD, which moved releases from "
        "monthly to weekly, and took front-end test coverage from 0 to 71% while reported production bugs fell 34%."
    ),
    (
        "I am studying computer security and forensics alongside this work, so threat modelling and least-privilege "
        "design are part of how I build rather than a review that happens at the end. My code and project write-ups "
        "are at github.com/lyle-mlengineer and lyle-mlengineer.github.io. I am in Nairobi (UTC+3), open to remote "
        "work with overlap for Kerugoya, and would be glad to walk through any of these systems in detail."
    ),
]


if __name__ == "__main__":
    base.build(AI_ML)
    base.build(FULLSTACK)

    build_letter(
        ROOT / "LYLE-OKOTH-ULINZI-AI-ML-COVER-LETTER.docx",
        "AI & Machine Learning — talent pipeline application",
        AI_ML_LETTER,
        "AI/ML Engineer — Computer Vision, Speech & Edge Inference",
    )
    build_letter(
        ROOT / "LYLE-OKOTH-ULINZI-FULLSTACK-COVER-LETTER.docx",
        "Software Development — full-stack engineer, talent pipeline application",
        FULLSTACK_LETTER,
        "Full-Stack Developer — Python, React & Secure Platforms",
    )
