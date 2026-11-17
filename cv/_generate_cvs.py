"""Generate ATS-friendly CVs (DOCX) for each role in the portfolio.

Rebuild:  python _generate_cvs.py
PDF:      "C:/Program Files/LibreOffice/program/soffice.exe" --headless --convert-to pdf --outdir . *.docx
"""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Pt, Inches, RGBColor

NAME = "LYLE OKOTH"
PHONE = "+254 797 668 066"
EMAIL = "lyleokoth.mlengineer@gmail.com"
LOCATION = "Nairobi, Kenya"
LINKS = [
    ("linkedin.com/in/lyle-okoth", "https://www.linkedin.com/in/lyle-okoth/"),
    ("github.com/lyle-mlengineer", "https://github.com/lyle-mlengineer"),
    ("lyle-mlengineer.github.io", "https://lyle-mlengineer.github.io"),
    ("medium.com/@lyle-okoth", "https://medium.com/@lyle-okoth"),
]
DARK = RGBColor(0x1F, 0x2A, 0x37)

EDUCATION = [
    ("BSc, Computer Security and Forensics (in progress)",
     "JOOUST", "2024 – 2028"),
    ("Diploma, Mechatronics Engineering (Upper Second Class)",
     "JKUAT, Juja, Kenya", "2016 – 2019"),
    ("Kenya Certificate of Secondary Education",
     "Friends School Kamusinga", "2012 – 2015"),
]
CERTS = "DeepLearning.AI, NVIDIA Deep Learning Institute, AWS and Google Cloud — 14 credentials (2021 – 2025)."


def add_hyperlink(paragraph, url, text, size=9.5):
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F6FB2")
    rpr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(underline)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rpr.append(sz)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def section_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text.upper())
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = DARK
    ppr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), "1F2A37")
    pbdr.append(bottom)
    ppr.append(pbdr)
    return p


def para(doc, text, bold=False, size=10.5, space_after=3, italic=False, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align:
        p.alignment = align
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    return p


def labeled(doc, label, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    r1 = p.add_run(label + ": ")
    r1.bold = True
    r1.font.size = Pt(10.5)
    r2 = p.add_run(text)
    r2.font.size = Pt(10.5)
    return p


def job_header(doc, title, company, dates):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(2)
    tab = p.paragraph_format.tab_stops
    tab.add_tab_stop(Inches(7.3), WD_TAB_ALIGNMENT.RIGHT)
    r1 = p.add_run(f"{title} — {company}")
    r1.bold = True
    r1.font.size = Pt(11)
    r2 = p.add_run("\t" + dates)
    r2.font.size = Pt(10.5)
    return p


def bullet(doc, text, lead_bold=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(1)
    if lead_bold:
        r = p.add_run(lead_bold)
        r.bold = True
        r.font.size = Pt(10.5)
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    return p


def build_doc():
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    doc.styles["List Bullet"].font.size = Pt(10.5)
    for s in doc.sections:
        s.top_margin = Inches(0.55)
        s.bottom_margin = Inches(0.55)
        s.left_margin = Inches(0.6)
        s.right_margin = Inches(0.6)
    return doc


def header(doc, headline, link_list=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(NAME)
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = DARK
    para(doc, headline, bold=True, size=11.5, space_after=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, f"{LOCATION}  |  {PHONE}  |  {EMAIL}", size=10, space_after=1, align=WD_ALIGN_PARAGRAPH.CENTER)

    links = doc.add_paragraph()
    links.alignment = WD_ALIGN_PARAGRAPH.CENTER
    links.paragraph_format.space_after = Pt(2)
    for i, (label, url) in enumerate(link_list or LINKS):
        if i:
            sep = links.add_run("  |  ")
            sep.font.size = Pt(9)
        add_hyperlink(links, url, label, size=9)


# ---------------------------------------------------------------------------
# Shared project write-ups, grounded in the READMEs in /home/lyle/git/portfolio
# ---------------------------------------------------------------------------
PROJECT_COAGENT = (
    "coAgent — Private Coding Agent for Colab",
    "Python coding agent for Google Colab's free T4: Qwen2.5-Coder-7B runs locally at NF4, plans inside the "
    "repository, edits with a tree-sitter map and BM25 retrieval, verifies with Ruff and pytest, and commits every "
    "checkpoint to an isolated git branch. Published on PyPI as co-agent-coder 0.2.1 — no API keys or per-token cost.",
    [("github.com/lyle-mlengineer/coagent", "https://github.com/lyle-mlengineer/coagent"),
     ("pypi.org/project/co-agent-coder", "https://pypi.org/project/co-agent-coder/")],
)

PROJECT_DOCENT = (
    "Docent — AI Product Guide",
    "Pre-launch AI product guide: explore a site, build an evidence-backed model of its workflows, narrate a "
    "walkthrough and guide users live. Shipped the public front door — FastAPI, PostgreSQL and Jinja2 with a durable "
    "waitlist, contact inbox, protected admin, CSV export, rate limits and a strict CSP.",
    [("docent-9a62.onrender.com", "https://docent-9a62.onrender.com/"),
     ("github.com/lyle-mlengineer/docent", "https://github.com/lyle-mlengineer/docent")],
)

PROJECT_SURAYA = (
    "Suraya — Diffusion Model for Kenyan Faces",
    "Audit-driven latent diffusion model for photorealistic 256×256 Kenyan faces: a compact 66M-parameter UNet on a "
    "frozen SD VAE, face-detect/align preprocessing, a VAE quality gate and KID-led evaluation, with an SDXL LoRA "
    "track for comparison. Pipeline complete and tested; training runs in Colab.",
    [("github.com/lyle-mlengineer/suraya", "https://github.com/lyle-mlengineer/suraya")],
)

PROJECT_SNAP = (
    "SnapToSpot — Website-to-Campaign Pipeline",
    "Turns a website into a five-platform campaign kit — stills, video, poster and copy deck — built only from facts "
    "the site can support. The model writes the words and structure, a deterministic renderer sets the type, and "
    "every number traces to a source span. FastAPI, PostgreSQL/pgvector, Alembic and OAuth2; in active development.",
    [("github.com/lyle-mlengineer/Snap2Spot", "https://github.com/lyle-mlengineer/Snap2Spot")],
)

PROJECT_VOCALIS = (
    "Vocalis — Voice Design Studio",
    "Brief-to-voice studio: describe a voice, design and audition it, refine the brief, organize albums and "
    "synthesize narration with rate, volume and style controls. Provider-agnostic Breeze and Fish Audio adapters, a "
    "credit ledger, idempotent M-Pesa and Stripe settlement, and a FastAPI + Jinja2 monolith.",
    [("github.com/lyle-mlengineer/vocalis", "https://github.com/lyle-mlengineer/vocalis"),
     ("vocalis-rvcw.onrender.com", "https://vocalis-rvcw.onrender.com")],
)

PROJECT_ECHOID = (
    "EchoID — Speaker-Aware Transcription Studio",
    "Upload → diarise → review → export. Speaker-labelled transcripts with timestamps, reusable speaker profiles, "
    "search and filters, and JSON, TXT or branded PDF exports. A pluggable transcription provider behind one JSON "
    "contract, credit billing with M-Pesa and Stripe, and a domain-driven FastAPI monolith.",
    [("github.com/lyle-mlengineer/echoid", "https://github.com/lyle-mlengineer/echoid"),
     ("echoid.onrender.com", "https://echoid.onrender.com")],
)

PROJECT_LABELSET = (
    "LabelSet — Audio Data Platform",
    "Audio-first sourcing and labelling platform: organizations, projects, tasks and a labeler marketplace across 11 "
    "speech task types, with background preprocessing into 60-second mono 16 kHz clips, review, KES billing and "
    "JSONL dataset export. FastAPI, PostgreSQL, SQLAlchemy and Jinja2.",
    [("github.com/lyle-mlengineer/labelset", "https://github.com/lyle-mlengineer/labelset"),
     ("labelset.onrender.com", "https://labelset.onrender.com")],
)

PROJECT_SAUTIFLOW = (
    "SautiFlow — Voice & Podcast Studio",
    "FastAPI podcast and voice-over studio: guest project creation, account and voice libraries, a responsive "
    "browser studio and credit-pack checkout, with project settings persisted to SQLite or PostgreSQL. The product "
    "surface that carries the speech stack.",
    [("sautiflow.co.ke", "https://www.sautiflow.co.ke/")],
)

PROJECT_FACEFORM = (
    "FaceForm — Synthetic Portrait Studio",
    "Brief-to-portrait studio: describe age, ethnicity, features and styling, then generate photoreal, clearly "
    "synthetic portraits through NVIDIA Flux. Gallery, albums, regenerate and refine, and pay-per-image credits with "
    "idempotent M-Pesa and Stripe settlement.",
    [("github.com/lyle-mlengineer/faceform", "https://github.com/lyle-mlengineer/faceform"),
     ("faceform-2rkf.onrender.com", "https://faceform-2rkf.onrender.com")],
)

PROJECT_PLUSONE = (
    "PlusOne — Personal AI Photography",
    "Builds a photo story from an event brief, the people in it and a few reference photos, keeping identities "
    "consistent across every shot. Studio, photo feed, albums and a credit ledger, backed by an agent pipeline with "
    "content-addressed dedupe, budget guards and partial-run recovery.",
    [("github.com/lyle-mlengineer/pigamagic-agent", "https://github.com/lyle-mlengineer/pigamagic-agent"),
     ("pigamagic.onrender.com", "https://pigamagic.onrender.com")],
)


ML_ENGINEER = {
    "file": "LYLE-OKOTH-MACHINE-LEARNING-ENGINEER.docx",
    "headline": "MACHINE LEARNING ENGINEER | SPEECH & VOICE AI",
    "summary": (
        "Machine Learning Engineer with four years of experience designing, training and productionising multilingual "
        "speech and vision systems — ASR, speech-to-speech translation, TTS and diffusion image models — for East "
        "African languages. Owns the full model lifecycle from data and evaluation to deployment: cut Swahili and "
        "Sheng ASR error rate from 23.4% to 11.8%, shipped streaming translation at 310 ms median first-audio "
        "latency, and raised TTS capacity to 42 concurrent voices per GPU. Builds the evaluation gates that keep "
        "regressions out of release."
    ),
    "competencies": [
        ("Speech & Voice AI", "ASR (Whisper, wav2vec 2.0, NeMo), TTS and voice design (VITS, XTTS-v2, Fish Audio, "
                              "Breeze), speech-to-speech translation (SeamlessM4T, NLLB-200), diarisation and VAD"),
        ("Vision & Generative Models", "Latent diffusion and flow matching, Stable Diffusion / SDXL, LoRA and "
                                       "DreamBooth, NVIDIA Flux, face detection and alignment, content provenance"),
        ("Modelling & Evaluation", "PyTorch training and distributed runs, LoRA / QLoRA fine-tuning, WER / CER / MOS "
                                   "evaluation, KID / FID, blind listening panels, experiment tracking (Weights & "
                                   "Biases, MLflow, Optuna)"),
        ("MLOps & Serving", "int8 / FP16 / NF4 quantisation, ONNX Runtime, TensorRT, Triton Inference Server, vLLM, "
                            "KV caching, continuous batching, CI regression gates, Docker, Kubernetes"),
    ],
    "tech": [
        ("Languages", "Python, C++, JavaScript/TypeScript, SQL"),
        ("Speech & ML", "PyTorch 2.x, Hugging Face Transformers, PEFT, Accelerate, Diffusers, ESPnet, Coqui TTS, "
                        "pyannote.audio, scikit-learn, Optuna"),
        ("Serving & Infra", "FastAPI, Triton Inference Server, ONNX Runtime, TensorRT, vLLM, gRPC / WebSocket "
                            "streaming, Redis, Celery, Docker, Kubernetes"),
        ("Data & MLOps", "Apache Spark, Kafka, Airflow, dbt, DVC, Great Expectations, Weights & Biases, MLflow, "
                         "PostgreSQL, Render"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Built Suraya, an audit-driven latent-diffusion pipeline for photoreal Kenyan faces: 889-image data "
                 "audit, face detect and align, a compact 66M UNet on a frozen SD VAE, and KID-led evaluation."),
                ("Shipped Vocalis and EchoID with provider-agnostic voice and transcription adapters, credit ledgers "
                 "and idempotent M-Pesa / Stripe settlement, evaluating provider output before release."),
                ("Wrote the evaluation and guardrail patterns clients keep using: offline quality gates, latency and "
                 "cost budgets, secret redaction and human approval for sensitive actions."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 hours of in-house audio."),
                ("Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs (English and Swahili, Luo and Kikuyu), down from a 1.4 s batch baseline."),
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
                ("Automated transcription alignment and diarisation pre-labelling, cutting human labelling from 11 to "
                 "3.5 minutes per hour of audio — a 68% saving adopted as the platform default."),
                ("Introduced DVC versioning with content hashing so every model release traces to an exact data "
                 "snapshot; consolidated 14 schemas into a dbt warehouse, cutting compute spend 23%."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ monthly users, "
                 "with REST and WebSocket APIs in Django and Node.js at p95 latency under 140 ms."),
                ("Introduced Docker deploys and GitHub Actions CI/CD — release cadence monthly to weekly, lead time 3 "
                 "weeks to 2 days — and took front-end test coverage from 0 to 71%."),
            ],
        },
    ],
    "projects": [PROJECT_VOCALIS, PROJECT_ECHOID, PROJECT_SURAYA],
    "education": EDUCATION,
    "certs": CERTS,
    "extra": None,
    "compact": True,
}

DATA_ENGINEER = {
    "file": "LYLE-OKOTH-DATA-ENGINEER.docx",
    "headline": "DATA ENGINEER | AUDIO & MULTIMODAL ML DATA",
    "summary": (
        "Data Engineer with four years of experience building the ingestion, alignment, labelling and versioning path "
        "that turns raw audio and images into training-ready datasets. Designed LabelSet, an audio-first sourcing and "
        "labelling platform with 11 speech task types and KES billing; built pipelines processing 6 TB / 38,000 hours "
        "of raw audio a year; and cut manual labelling time 68%. Owns data quality, consent, retention and PII "
        "redaction, with the software background (APIs at 1.2M requests a day) to keep pipelines operable in "
        "production."
    ),
    "competencies": [
        ("Pipeline Engineering", "Batch ETL / ELT, streaming and event-driven jobs, Spark tuning for audio shards, "
                                 "Parquet / Arrow data lakes, Delta Lake, Airflow and Kafka orchestration, dbt and "
                                 "DuckDB modelling"),
        ("Data Quality & Governance", "Great Expectations checks, DVC versioning with content hashing, dataset cards "
                                      "and lineage from raw file to training shard, speaker consent, retention and "
                                      "PII-redaction flows"),
        ("ML Data Support", "Transcription alignment, diarisation pre-labelling, forced alignment, human + AI "
                            "collaborative annotation, synthetic data generation, dataset tuning for ASR, TTS and "
                            "translation training"),
        ("Platform & Reliability", "PostgreSQL, S3-compatible object storage, Redis, Terraform, Docker, Kubernetes, "
                                   "FFmpeg pipelines, on-call observability: monthly restores replaced by daily "
                                   "automated checks"),
    ],
    "tech": [
        ("Languages", "Python, SQL, JavaScript/TypeScript, C++"),
        ("Processing", "Apache Spark, Kafka, Airflow, dbt, DuckDB, Polars / Pandas, Celery, FFmpeg"),
        ("Storage & Warehousing", "PostgreSQL, BigQuery, AWS S3, GCS, Parquet / Arrow, Delta Lake, Elasticsearch, Redis"),
        ("Quality & Versioning", "Great Expectations, DVC, data contracts, dataset cards and lineage"),
        ("Infrastructure", "Docker, Kubernetes, Terraform, GitHub Actions CI/CD, AWS, GCP, Render"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Built LabelSet's audio-first data platform: organizations, projects, tasks and a labeler "
                 "marketplace, with background preprocessing into 60-second mono 16 kHz clips and JSONL dataset "
                 "export."),
                ("Implemented KES billing for organizations and labelers, with provider-confirmed top-ups, atomic "
                 "task settlement and signed payment webhooks."),
                ("Built SnapToSpot's fact-grounded pipeline: crawl → site profile → facts and conflicts → deterministic "
                 "render, with a source span behind every number."),
                ("Built Suraya's dataset audit and preprocessing: an 889-image audit, face detect and align, 256 px "
                 "crops, a VAE quality gate and reproducible dataset versioning."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Own the speech model lifecycle end to end; the data foundation built in this role feeds all model "
                 "training — 1,240 curated hours drove a Whisper ASR fine-tune that cut WER from 23.4% to 11.8%."),
                ("Built the audio collection, editing and annotation platform with AI-assisted pre-labelling, and "
                 "published 3 open datasets to Hugging Face (18,000+ downloads)."),
                ("Run one evaluation harness across 5 ASR models, processing an hour of four-speaker audio in 4 minutes "
                 "on a single GPU and 40,000 hours indexed for production tenants."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Designed batch and streaming pipelines with Apache Spark, Airflow and Kafka processing 6 TB / 38,000 "
                 "hours of raw audio a year into training-ready datasets for ASR, translation and TTS models."),
                ("Automated transcription alignment and diarisation pre-labelling, cutting human labelling time from 11 "
                 "to 3.5 minutes per hour of audio — a 68% saving adopted as the platform's default workflow."),
                ("Introduced dataset versioning with DVC and content hashing so every model release traces to an exact "
                 "data snapshot, eliminating reproducibility disputes across the ML team."),
                ("Consolidated 14 scattered schemas into a single dbt-modelled warehouse, reducing pipeline failures "
                 "41% and monthly compute spend 23%."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Built and maintained REST and WebSocket APIs in Django and Node.js serving 1.2M requests a day at "
                 "p95 latency under 140 ms, with PostgreSQL, Redis and Twilio voice/SMS integrations."),
                ("Introduced Docker deployments and a GitHub Actions CI/CD pipeline: release cadence moved from monthly "
                 "to weekly and lead time dropped from 3 weeks to 2 days."),
            ],
        },
    ],
    "projects": [PROJECT_LABELSET, PROJECT_SNAP, PROJECT_SURAYA],
    "education": EDUCATION,
    "certs": CERTS,
    "extra": None,
    "compact": True,
}

SOFTWARE_ENGINEER = {
    "file": "LYLE-OKOTH-SOFTWARE-ENGINEER.docx",
    "headline": "SOFTWARE ENGINEER | FULL-STACK & AI PRODUCTS",
    "summary": (
        "Software Engineer with four years of experience shipping voice-first and AI-native products end to end — "
        "requirement framing, UI/UX, backend APIs, deployment and iteration. Built IVR and WhatsApp assistants "
        "serving 40,000+ monthly users, REST and WebSocket APIs handling 1.2M requests a day at p95 latency under "
        "140 ms, and Docker + GitHub Actions CI/CD that moved releases from monthly to weekly. Now builds multi-tenant "
        "FastAPI products with credit ledgers, M-Pesa / Stripe billing and LLM and agent features."
    ),
    "competencies": [
        ("Backend", "REST and WebSocket APIs, FastAPI / Django / Flask / Node.js, OAuth2 and PKCE, payment webhooks, "
                    "idempotent settlement, USSD menus, Twilio voice and SMS, real-time streaming services"),
        ("Frontend & Product", "Server-rendered Jinja2 and React interfaces, UI/UX design, AI-assisted onboarding, "
                               "responsive studios and dashboards, documentation that speeds up onboarding"),
        ("Platform & Reliability", "Docker, GitHub Actions CI/CD, Kubernetes, Render deployments, Postgres and Redis, "
                                   "logging, tracing and cost monitoring, CSP and rate-limiting defaults"),
        ("AI Integration", "Model services behind FastAPI, provider-agnostic model adapters, credit ledgers, LLM and "
                           "agent workflows, retrieval, evaluation hooks and human approval"),
    ],
    "tech": [
        ("Languages", "Python, JavaScript/TypeScript, C++, SQL"),
        ("Frameworks", "FastAPI, Django, Flask, Node.js, React, Next.js, Jinja2"),
        ("Data & Messaging", "PostgreSQL, SQLite, Redis, Elasticsearch, Apache Kafka, Celery, Alembic"),
        ("DevOps & Cloud", "Docker, Kubernetes, GitHub Actions CI/CD, Render, AWS, GCP"),
        ("Other", "Twilio, M-Pesa Daraja, Stripe, WebSocket streaming, scikit-learn, Hugging Face, NVIDIA Flux"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Built coAgent Web and Docent: FastAPI + Jinja2 front doors with Postgres-backed waitlists, GitHub "
                 "OAuth / PKCE, rate limits, CSP, honeypots and graceful database failure."),
                ("Built SnapToSpot: a multi-tenant FastAPI service with OAuth2, tenant-scoped sites, Alembic migrations "
                 "and a background pipeline that turns a URL into a reviewed campaign kit."),
                ("Shipped Vocalis, EchoID and FaceForm: server-rendered studios, credit ledgers, M-Pesa and Stripe "
                 "checkout, and provider adapters behind one typed contract."),
                ("Built PlusOne's product shell — studio, photo feed, albums, credits — and its rendering agent with "
                 "content-addressed dedupe and partial-run recovery."),
            ],
        },
        {
            "title": "Machine Learning Engineer (full-stack responsibilities)",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Worked with software engineers to design and ship web interfaces for real-time streaming translation, "
                 "transcription and synthesis; SautiFlow now serves 2,100 monthly creators at 61% week-four retention."),
                ("Deployed model services (FastAPI, Triton, Kubernetes) serving streaming speech at 310 ms median "
                 "first-audio latency; instrumented logging and tracing to monitor token usage and detect model drift."),
                ("Built authentication and authorisation controls that blocked bot API misuse without adding friction "
                 "for real users, and wrote the guardrail specs now used across model endpoints."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Built a fast, scalable synchronous and asynchronous backend for real-time and batch processing of user "
                 "requests, plus the data studio for human + AI collaborative data collection and annotation."),
                ("Designed pipelines (Airflow, Kafka, Spark) processing 6 TB of audio a year and wrote the documentation "
                 "that made onboarding new hires easier."),
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
    "projects": [PROJECT_SAUTIFLOW, PROJECT_DOCENT, PROJECT_PLUSONE],
    "education": EDUCATION,
    "certs": CERTS,
    "extra": ("LEADERSHIP", ["Co-Founder — SautiFlow Labs (2022)", "Volunteer — OMDENA (2024)",
                             "Founded a 12-member coding club and ran weekend build sessions"]),
    "compact": True,
}


AI_ENGINEER = {
    "file": "LYLE-OKOTH-AI-ENGINEER.docx",
    "headline": "AI ENGINEER | APPLIED AI, AGENTS & SPEECH",
    "summary": (
        "AI Engineer with four years of experience taking applied AI products from prototype to production — LLM "
        "agents, retrieval, speech and vision systems, and the backend, evaluation and deployment work around them. "
        "Built and shipped coAgent (a private coding agent for Colab), Docent (an AI product guide), Suraya (a "
        "diffusion model for Kenyan faces) and Vocalis (a voice-design studio)."
    ),
    "competencies": [
        ("Applied AI & Agents", "LLM agents, tool use and function calling, planning / verification loops, retrieval "
                                "augmented generation (BM25 + vector search), prompt design, evaluation harnesses, "
                                "guardrails, human approval, secret redaction"),
        ("Speech & Multimodal", "ASR, speaker diarisation and embeddings, TTS and voice design, diffusion image "
                                "generation (Stable Diffusion, SDXL, NVIDIA Flux), face detection and alignment, "
                                "quality gates and content provenance"),
        ("Modelling & Optimisation", "PyTorch training and fine-tuning, LoRA / QLoRA, NF4 and int8 quantisation, "
                                     "ONNX Runtime, TensorRT, KV caching, batching, KID / FID, WER / CER / MOS, "
                                     "latency and cost profiling"),
        ("AI Platform & Product", "FastAPI model services, PostgreSQL, Redis, Celery, Docker, Kubernetes, GitHub "
                                  "Actions, Render, AWS / GCP, credit ledgers, idempotent M-Pesa and Stripe payments, "
                                  "technical writing and handover"),
    ],
    "tech": [
        ("Languages", "Python, TypeScript/JavaScript, SQL, C++"),
        ("AI & ML", "PyTorch, Hugging Face Transformers, PEFT, Diffusers, scikit-learn, Whisper, Qwen2.5-Coder, "
                    "NVIDIA Flux, Stable Diffusion / SDXL"),
        ("Inference & Evaluation", "bitsandbytes NF4, int8 / FP16 quantisation, ONNX Runtime, TensorRT, Triton, "
                                   "vLLM, KV caching, KID / FID, WER / CER / MOS, offline and online evaluation"),
        ("Backend, Data & Cloud", "FastAPI, Jinja2, PostgreSQL, Redis, Celery, Elasticsearch, Spark, Kafka, Docker, "
                                  "Kubernetes, Render, AWS, GCP, Weights & Biases, MLflow, DVC"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Partner with founders and product teams to scope, build and ship AI features end to end — data, model "
                 "selection, evaluation, inference, UI and deployment — leaving behind runbooks the client's team can "
                 "own."),
                ("Built coAgent, a private coding agent for Google Colab's free T4: local Qwen2.5-Coder-7B inference at "
                 "NF4, a survey → plan → act → verify loop, tree-sitter and BM25 repository retrieval, Ruff + pytest "
                 "verification and git-backed checkpoints; published 0.2.1 to PyPI as co-agent-coder."),
                ("Shipped Docent's public front door — FastAPI, PostgreSQL, Jinja2 and vanilla JavaScript — with a "
                 "durable waitlist, contact inbox, protected admin surface, CSV export, rate limits and a strict CSP."),
                ("Built Suraya, an audit-driven latent-diffusion pipeline for Kenyan faces: a compact 66M UNet on a "
                 "frozen SD VAE, face-detect/align preprocessing and KID-led evaluation; pipeline complete and tested."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 hours of in-house audio."),
                ("Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs (English and Swahili, Luo and Kikuyu), down from a 1.4 s batch baseline."),
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
                ("Automated transcription alignment and diarisation pre-labelling, cutting human labelling from 11 to "
                 "3.5 minutes per hour of audio — a 68% saving adopted as the platform default."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ monthly users, "
                 "with REST and WebSocket APIs in Django and Node.js at p95 latency under 140 ms."),
                ("Introduced Docker deploys and GitHub Actions CI/CD — release cadence monthly to weekly, lead time 3 "
                 "weeks to 2 days — and took front-end test coverage from 0 to 71%."),
            ],
        },
    ],
    "projects": [PROJECT_COAGENT, PROJECT_DOCENT, PROJECT_SURAYA],
    "education": EDUCATION,
    "certs": CERTS,
    "extra": None,
    "compact": True,
}


AI_ML_ENGINEER = {
    "file": "LYLE-OKOTH-AI-ML-ENGINEER.docx",
    "headline": "AI/ML ENGINEER | LLM AGENTS, RAG & PRODUCTION PLATFORMS",
    "summary": (
        "AI/ML Engineer with four years of experience shipping LLM agents and AI products end to end. Built coAgent, "
        "a private coding agent with a five-phase tool loop, repository retrieval and test-driven verification, "
        "published on PyPI; SnapToSpot, a multi-tenant pipeline that grounds every generated claim in a retrieved "
        "source; and PlusOne, an agent pipeline with budget guards and partial-run recovery. Strong Python, FastAPI "
        "and PostgreSQL, with hands-on RAG, evaluation and deployment on AWS, GCP and Render."
    ),
    "competencies": [
        ("LLM Agents & Orchestration", "Planning and verification loops, tool and function calling, structured "
                                        "outputs, RAG with BM25 and vector search, agent state machines, human "
                                        "approval and guardrails; LangChain / LangGraph / LlamaIndex patterns"),
        ("Python Backend & APIs", "FastAPI, Django and Flask services, REST and WebSocket APIs, OAuth2 / JWT and "
                                   "Pydantic contracts, SQLAlchemy and Alembic, multi-tenant isolation, background "
                                   "jobs, idempotent webhooks and payment settlement"),
        ("Evaluation & Experimentation", "Offline and online evaluation, task-success and regression suites, "
                                          "WER / CER / MOS and KID / FID, latency and cost budgets, prompt and model "
                                          "comparisons, CI quality gates and experiment tracking"),
        ("Production & Cloud", "Docker, Kubernetes, GitHub Actions, Render, AWS and GCP, PostgreSQL, Redis and "
                                "Celery, observability for token usage and drift, rate limits, CSP, caching and "
                                "graceful degradation"),
    ],
    "tech": [
        ("Languages", "Python, TypeScript/JavaScript, SQL, C++"),
        ("LLM & Agents", "OpenAI-compatible APIs, Qwen2.5-Coder, Hugging Face Transformers, LangChain / LangGraph / "
                         "LlamaIndex (working knowledge), tool calling, RAG, pgvector, BM25"),
        ("Backend & Data", "FastAPI, Django, Flask, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, "
                           "Elasticsearch"),
        ("MLOps & Cloud", "PyTorch, PEFT / LoRA, bitsandbytes NF4, ONNX Runtime, TensorRT, Triton, vLLM, MLflow, "
                          "Weights & Biases, Docker, Kubernetes, AWS, GCP"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Built coAgent, a private coding agent for Colab's free T4: a survey → plan → act → verify → report "
                 "loop, Qwen2.5-Coder-7B at NF4, tree-sitter and BM25 retrieval, Ruff and pytest verification, and a "
                 "git checkpoint per verified step; published 0.2.1 to PyPI."),
                ("Built SnapToSpot, a multi-tenant FastAPI service (OAuth2, Alembic, PostgreSQL/pgvector) that turns a "
                 "website into a campaign kit, rendering only facts that trace to an accepted source."),
                ("Built PlusOne's agent pipeline: typed event stream, content-addressed photo store, budget-aware "
                 "orchestration and resumable runs that return completed work with refunds instead of losing it."),
                ("Shipped Vocalis, EchoID and FaceForm with provider-agnostic model adapters, credit ledgers, "
                 "idempotent M-Pesa and Stripe settlement, and evaluation of provider output before release."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 curated hours, comparing runs on held-out and noisy field sets before promotion."),
                ("Built the evaluation harness — WER, CER, MOS and CI regression gates — which blocked 9 model "
                 "regressions from release in two quarters and set the experiment-tracking standard across 60+ runs "
                 "a month."),
                ("Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs, deploying model services on FastAPI, Triton and Kubernetes."),
                ("Compressed a 1.6 GB TTS checkpoint to 480 MB with int8 quantisation and KV caching: 42 concurrent "
                 "voices per GPU, 3.1x throughput and 58% lower inference cost."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Designed batch and streaming pipelines (Airflow, Kafka, Spark) processing 6 TB / 38,000 hours of raw "
                 "audio a year into training-ready datasets."),
                ("Introduced DVC versioning with content hashing so every model release traces to an exact data "
                 "snapshot; consolidated 14 schemas into a dbt warehouse, cutting compute spend 23%."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Built REST and WebSocket APIs in Django and Node.js handling 1.2M requests a day at p95 latency "
                 "under 140 ms, and introduced Docker deploys with GitHub Actions CI/CD."),
                ("Took front-end test coverage from 0 to 71% and cut reported production bugs 34% by adding "
                 "regression tests around the payment and voice flows."),
            ],
        },
    ],
    "projects": [PROJECT_COAGENT, PROJECT_SNAP, PROJECT_PLUSONE],
    "education": EDUCATION,
    "certs": CERTS,
    "extra": None,
    "references": False,
    "compact": True,
}


ML_RESEARCHER = {
    "file": "LYLE-OKOTH-ML-RESEARCHER.docx",
    "headline": "MACHINE LEARNING RESEARCHER | SPEECH, GENERATIVE MODELS & EVALUATION",
    "summary": (
        "Machine Learning Researcher with four years of experience designing experiments, curating low-resource "
        "datasets and evaluating speech and generative models. Designed an audit-driven diffusion study for Kenyan "
        "faces — a compact 66M UNet against an SDXL LoRA baseline, with KID-led evaluation and a VAE quality gate — "
        "and built the 1,240-hour Swahili and Sheng corpus behind a Whisper-large-v3 fine-tune that cut WER from "
        "23.4% to 11.8%. Established the team's evaluation harness and published 3 datasets and 2 fine-tuned models "
        "on Hugging Face."
    ),
    "competencies": [
        ("Research Areas", "Multilingual and low-resource ASR, speech synthesis and voice design, speech translation, "
                           "speaker diarisation, latent diffusion and flow matching, evaluation methodology and "
                           "efficient inference"),
        ("Experimental Method", "Controlled ablations against strong baselines, held-out and noisy out-of-domain test "
                                "sets, WER / CER / MOS and KID / FID comparison, error analysis, reproducibility "
                                "checklists and dataset documentation"),
        ("Modelling", "PyTorch, Hugging Face Transformers and Diffusers, LoRA / QLoRA and DreamBooth, Whisper, "
                      "wav2vec 2.0, NVIDIA NeMo, VITS, XTTS-v2, SeamlessM4T, pyannote.audio, scikit-learn"),
        ("Compute & Tooling", "Distributed training (DDP / FSDP), mixed precision (FP16 / BF16), Colab T4 and cloud "
                              "GPUs, ONNX Runtime, TensorRT, Triton, vLLM, Weights & Biases, MLflow, Optuna, DVC, "
                              "technical writing"),
    ],
    "tech": [
        ("Languages", "Python, C++, SQL, JavaScript/TypeScript"),
        ("Frameworks", "PyTorch 2.x, Hugging Face Transformers, Diffusers, PEFT, Accelerate, ESPnet, NeMo, Coqui "
                       "TTS, pyannote.audio, torchaudio, librosa, scikit-learn"),
        ("Training & Evaluation", "DDP / FSDP, AMP (FP16 / BF16), LoRA / QLoRA, DreamBooth, Optuna, Weights & Biases, "
                                  "MLflow, DVC, WER / CER / MOS, KID / FID, blind listening panels"),
        ("Serving & Data", "ONNX Runtime, TensorRT, Triton, vLLM, int8 / FP16 / NF4, KV caching, Spark, Kafka, "
                           "Airflow, dbt, PostgreSQL, Docker, Kubernetes, AWS, GCP"),
    ],
    "jobs": [
        {
            "title": "Independent Researcher & AI Engineer",
            "company": "Freelance, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Designed Suraya, a data-scale study of Kenyan face generation: an 889-image audit that set "
                 "resolution, crop and augmentation policy, a compact 66M UNet on a frozen SD VAE, a paired SDXL "
                 "LoRA track, and a VAE quality gate with KID-led comparison, so the comparison is the deliverable."),
                ("Built LabelSet, a dataset platform covering 11 speech task types — transcription, translation, "
                 "diarisation, voice design and cloning, speech description, benchmarks and RL environments — with "
                 "16 kHz preprocessing, review and JSONL export."),
                ("Shipped Vocalis and EchoID on provider-agnostic voice and transcription adapters, so competing "
                 "models can be compared under one contract, and published the resulting datasets and checkpoints."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 curated hours, comparing held-out and noisy field sets before promoting a checkpoint."),
                ("Designed the evaluation protocol the team now uses — WER, CER, MOS and CI regression gates across 5 "
                 "ASR models — which blocked 9 model regressions from release in two quarters."),
                ("Benchmarked streaming speech-to-speech translation to 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs on a single T4, against a 1.4 s batch baseline."),
                ("Studied compression trade-offs for TTS: int8 quantisation and KV caching took a 1.6 GB checkpoint to "
                 "480 MB at 42 concurrent voices per GPU and 3.1x throughput, checked against the float baseline."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Built the corpus behind the research programme: Spark, Airflow and Kafka pipelines turning 6 TB / "
                 "38,000 hours of raw audio a year into training-ready ASR, translation and TTS datasets, versioned "
                 "with DVC content hashing."),
                ("Ran the pre-labelling study behind a 68% labelling reduction — alignment and diarisation models took "
                 "human effort from 11 to 3.5 minutes per audio hour — and shipped it as the platform default."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Trained the team's first model — a scikit-learn intent classifier that deflected 28% of support "
                 "chats — and instrumented the telemetry later used to evaluate model and product changes."),
                ("Shipped 5 production features for an IVR and WhatsApp assistant serving 40,000+ monthly users, and "
                 "introduced Docker deploys and GitHub Actions CI/CD, moving releases from monthly to weekly."),
            ],
        },
    ],
    "projects": [PROJECT_SURAYA, PROJECT_LABELSET],
    "education": EDUCATION,
    "certs": CERTS,
    "extra": ("Research Output", [
        "3 open speech datasets and 2 fine-tuned models on Hugging Face (18,000+ downloads).",
        "Reference evaluation harness — WER, CER, MOS and CI gates — reused across team and client projects.",
        "Public technical write-ups on ASR fine-tuning, diffusion evaluation and inference optimisation.",
    ]),
    "references": False,
    "compact": True,
}

def build(cv):
    doc = build_doc()
    header(doc, cv["headline"], cv.get("links"))

    section_heading(doc, "Professional Summary")
    para(doc, cv["summary"], space_after=4)

    section_heading(doc, "Core Competencies")
    for label, text in cv["competencies"]:
        labeled(doc, label, text)

    section_heading(doc, "Technical Skills")
    for label, text in cv["tech"]:
        labeled(doc, label, text)

    section_heading(doc, "Professional Experience")
    for job in cv["jobs"]:
        job_header(doc, job["title"], job["company"], job["dates"])
        for b in job["bullets"]:
            bullet(doc, b)

    section_heading(doc, "Selected Projects")
    for name, desc, links in cv["projects"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(name + " — ")
        r.bold = True
        r.font.size = Pt(10.5)
        r2 = p.add_run(desc)
        r2.font.size = Pt(10.5)
        if links:
            lp = doc.add_paragraph()
            lp.paragraph_format.space_after = Pt(2)
            for i, (text, url) in enumerate(links):
                if i:
                    sep = lp.add_run("  ·  ")
                    sep.font.size = Pt(9)
                add_hyperlink(lp, url, text, size=9)

    section_heading(doc, "Education")
    for title, school, dates in cv["education"]:
        job_header(doc, title, school, dates)

    section_heading(doc, "Certifications")
    para(doc, cv["certs"], space_after=4)

    if cv["extra"]:
        section_heading(doc, cv["extra"][0])
        for item in cv["extra"][1]:
            bullet(doc, item)

    if cv.get("references", True):
        refs = para(doc, "References available on request.", size=9.5, space_after=0, italic=True)
        refs.paragraph_format.space_before = Pt(6)

    if cv.get("compact"):
        for style_name in ("Normal", "List Bullet"):
            doc.styles[style_name].font.size = Pt(10)
        for s in doc.sections:
            s.top_margin = Inches(0.45)
            s.bottom_margin = Inches(0.45)
            s.left_margin = Inches(0.5)
            s.right_margin = Inches(0.5)
        for p in doc.paragraphs:
            for r in p.runs:
                if r.font.size:
                    r.font.size = Pt(max(8.5, r.font.size.pt - 0.5))
            pf = p.paragraph_format
            if pf.space_before is not None:
                pf.space_before = Pt(pf.space_before.pt * 0.75)
            if pf.space_after is not None:
                pf.space_after = Pt(pf.space_after.pt * 0.75)

    doc.save(cv["file"])
    print("saved", cv["file"])


if __name__ == "__main__":
    for cv in (AI_ENGINEER, ML_ENGINEER, ML_RESEARCHER, DATA_ENGINEER, SOFTWARE_ENGINEER, AI_ML_ENGINEER):
        build(cv)
