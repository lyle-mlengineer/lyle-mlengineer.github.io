"""Generate ATS-friendly CVs (DOCX) for each role in the portfolio.

Rebuild:  python _generate_cvs.py
PDF:      "C:/Program Files/LibreOffice/program/soffice.exe" --headless --convert-to pdf --outdir . *.docx
"""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, RGBColor

NAME = "LYLE OKOTH"
PHONE = "+254 797 668 066"
EMAIL = "lyleokoth.mlengineer@gmail.com"
LOCATION = "Nairobi, Kenya"
LINKS = "linkedin.com/in/lyle-okoth  |  github.com/lyle-mlengineer  |  lyle-mlengineer.github.io  |  medium.com/@lyle-okoth"
DARK = RGBColor(0x1F, 0x2A, 0x37)


def section_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
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
    p.paragraph_format.space_before = Pt(6)
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
    p.paragraph_format.space_after = Pt(2)
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


def header(doc, headline):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(NAME)
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = DARK
    para(doc, headline, bold=True, size=11.5, space_after=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, f"{LOCATION}  |  {PHONE}  |  {EMAIL}", size=10, space_after=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, LINKS, size=10, space_after=2, align=WD_ALIGN_PARAGRAPH.CENTER)


ML_ENGINEER = {
    "file": "LYLE-OKOTH-MACHINE-LEARNING-ENGINEER.docx",
    "headline": "MACHINE LEARNING ENGINEER | SPEECH & AUDIO PROCESSING",
    "summary": (
        "Machine Learning Engineer with 6+ years of experience designing, training and productionising "
        "multilingual speech systems — automatic speech recognition, speech-to-speech translation and text-to-speech "
        "synthesis — for East African languages. Owns the full model lifecycle (data, training, evaluation, "
        "deployment): halved Swahili/Sheng ASR error rates, shipped real-time speech translation at 310 ms median "
        "latency, and cut inference costs 58% through quantisation. Backed by deep software and data engineering "
        "roots, and published open datasets and models with 18,000+ downloads on Hugging Face."
    ),
    "competencies": [
        ("Core ML", "ASR (Whisper), TTS & voice cloning, speech-to-speech translation, transformer architectures, "
                    "diffusion & flow-matching models, LLM fine-tuning (LoRA / QLoRA), RLHF & preference optimisation, "
                    "synthetic data generation, multilingual & low-resource speech"),
        ("Speech Engineering", "Speaker diarisation, VAD, voice embeddings, streaming inference, latency optimisation, "
                    "time-to-first-token budgets, model evaluation (WER, CER, MOS)"),
        ("MLOps", "Experiment tracking (W&B), model registry, CI regression gates, quantisation (int8), "
                  "TensorRT/ONNX, GPU serving (CUDA, Triton), Kubernetes, monitoring & model-drift detection"),
        ("Data & Product", "Audio data collection, alignment & annotation platforms, dataset versioning (DVC), "
                 "data-quality frameworks, research-to-production, technical writing, UI design for speech products"),
    ],
    "tech": [
        ("Languages", "Python, C++, JavaScript/TypeScript, SQL"),
        ("ML Frameworks", "PyTorch, Hugging Face Transformers, Diffusers, scikit-learn, LoRA/PEFT, NLTK, spaCy"),
        ("Serving & Infra", "FastAPI, Triton Inference Server, CUDA, TensorRT, ONNX, WebRTC, Redis, Celery"),
        ("Data & MLOps", "Apache Spark, Kafka, Airflow, dbt, DVC, Great Expectations, Weights & Biases, Docker, Kubernetes, Terraform"),
        ("Cloud", "AWS (S3, GPU instances), GCP"),
    ],
    "jobs": [
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 hours of in-house audio — the company's first production-grade transcription product for East Africa."),
                ("Architected and shipped streaming speech-to-speech translation at 310 ms median first-audio latency "
                 "(p95 780 ms) on a single T4 GPU — a 4.5x improvement over the 1.4 s batch baseline."),
                ("Compressed a 1.6 GB TTS checkpoint to 480 MB using int8 quantisation and KV caching, raising capacity "
                 "to 42 concurrent voices per GPU and cutting inference cost by 58%."),
                ("Built the model evaluation harness (WER, CER, MOS with CI regression gates), blocking 9 model "
                 "regressions from release across two quarters."),
                ("Published 3 open speech datasets and 2 fine-tuned models to Hugging Face, reaching 18,000+ downloads "
                 "in the first quarter."),
                ("Built an audio data collection, editing and annotation platform leveraging fine-tuned audio models for "
                 "AI pre-labelling, reducing human labelling time by 68%."),
                ("Developed speaker diarisation, VAD and voice-embedding pipelines for multi-speaker meeting audio, and "
                 "RL preference-tuning guardrails against prompt injection and model misuse."),
                ("Set the team's model-card and experiment-tracking standard across 60+ training runs per month; "
                 "implemented latest speech research to keep models close to state of the art."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2024",
            "bullets": [
                ("Designed batch and streaming pipelines (Airflow, Kafka, Spark) processing 6 TB / 38,000 hours of raw "
                 "audio per year into training-ready speech datasets."),
                ("Automated transcription alignment and diarisation pre-labelling, cutting human labelling from 11 to "
                 "3.5 minutes per hour of audio; introduced DVC dataset versioning so every model release traces to an "
                 "exact data snapshot."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2020 – 2022",
            "bullets": [
                ("Shipped full-stack features for IVR and WhatsApp voice assistants serving 40,000+ monthly users, and "
                 "trained the team's first production model — a FastAPI-served intent classifier deflecting 28% of "
                 "support chats."),
            ],
        },
    ],
    "projects": [
        ("Vocalis — Brand Voice Studio", "Voice-cloning TTS service: one licensed studio read in, a reusable brand voice out, "
            "served over an API. Built for African-accented English and local-language narration that vendor catalogs "
            "do not cover."),
        ("EchoID — Speaker Attribution", "Turns unlabelled audio archives into speaker-labelled, searchable transcripts "
            "using diarisation, voice embeddings and ASR — queryable by legal, research and support teams."),
        ("LabelSet — Speech Data Platform", "End-to-end data pipeline behind every model shipped: sourcing recordings, "
            "human + AI collaborative labelling, and quality verification before training."),
        ("FaceForm — Synthetic Face Generator", "Generates consistent, clearly synthetic faces for teams that need people "
            "in their visuals without licensing real ones — a designer sets an archetype once, then draws a whole "
            "persona family from the same latent noise."),
    ],
    "education": [
        ("BSc, Computer Security and Forensics", "Jaramogi Oginga Odinga University of Science and Technology (JOOUST)", "2016 – 2020"),
        ("Diploma, Mechatronics Engineering", "JKUAT, Juja, Kenya", "2013 – 2016"),
    ],
    "certs": "DeepLearning.AI, NVIDIA Deep Learning Institute, AWS and Google Cloud professional certifications (2021 – 2025).",
    "extra": None,
}

DATA_ENGINEER = {
    "file": "LYLE-OKOTH-DATA-ENGINEER.docx",
    "headline": "DATA ENGINEER | AUDIO & ML DATA PIPELINES",
    "summary": (
        "Data Engineer with 6+ years of experience building batch and streaming pipelines that turn raw, noisy audio "
        "into training-ready datasets at scale — 6 TB / 38,000 hours per year — for machine learning teams. Owns "
        "ingestion, alignment, labelling, versioning and data quality end to end, with hands-on software engineering "
        "(APIs at 1.2M requests/day) and ML experience that keeps pipelines tuned for model training, not just "
        "analytics. Cut human data-labelling time 68% through automation and reduced pipeline failures 41% by "
        "consolidating 14 scattered schemas into a dbt-modelled warehouse."
    ),
    "competencies": [
        ("Pipeline Engineering", "Batch ETL / ELT, streaming & event-driven jobs, Spark tuning for audio shards, "
                                 "Parquet/Arrow data lakes, feature stores, orchestration with Airflow and Dagster-style "
                                 "dependency graphs"),
        ("Data Quality & Governance", "Great Expectations checks, dataset versioning (DVC) + content hashing, schema "
                                      "consolidation with dbt, speaker consent, retention and PII-redaction flows for "
                                      "40,000+ hours of stored audio"),
        ("ML Data Support", "Transcription alignment, diarisation pre-labelling, human + AI collaborative annotation "
                            "platforms, synthetic data generation, data pipelines tuned for ASR/TTS/translation training"),
        ("Platform & Reliability", "AWS S3, GCS, PostgreSQL, Elasticsearch, Redis, Kafka, Terraform, Docker, on-call "
                                   "and observability: moved from monthly restores to daily automated checks"),
    ],
    "tech": [
        ("Languages", "Python, SQL, JavaScript/TypeScript, C++"),
        ("Processing", "Apache Spark, Kafka, Airflow, dbt, DuckDB, Flink-style streaming, Celery"),
        ("Storage & Warehousing", "PostgreSQL, AWS S3, GCS, Parquet / Arrow, Elasticsearch, Redis"),
        ("Quality & Versioning", "Great Expectations, DVC, content hashing, data contracts"),
        ("Infrastructure", "Docker, Kubernetes, Terraform, GitHub Actions CI/CD, AWS, GCP"),
    ],
    "jobs": [
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2024",
            "bullets": [
                ("Designed batch and streaming pipelines with Apache Spark, Airflow and Kafka processing 6 TB / 38,000 "
                 "hours of raw audio per year into training-ready datasets for ASR, translation and TTS models."),
                ("Automated transcription alignment and diarisation pre-labelling, cutting human labelling time from 11 "
                 "to 3.5 minutes per hour of audio — a 68% saving adopted as the platform's default workflow."),
                ("Introduced dataset versioning with DVC and content hashing so every model release traces to an exact "
                 "data snapshot, eliminating reproducibility disputes across the ML team."),
                ("Consolidated 14 scattered schemas into a single dbt-modelled warehouse, reducing pipeline failures by "
                 "41% and monthly compute spend by 23%."),
                ("Built data-quality runbooks (Great Expectations) and onboarded 3 team members; owned speaker consent, "
                 "retention and PII-redaction flows for 40,000+ hours of stored audio."),
                ("Engineered feature stores and Parquet data lakes tuned for audio shards rather than tabular rows; "
                 "moved pipeline reliability from monthly restores to daily automated checks."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Own the speech model lifecycle end to end; the data foundation built in this role feeds all model "
                 "training — 1,240 hours of curated audio drove a Whisper ASR fine-tune that cut WER from 23.4% to 11.8%."),
                ("Built the audio data collection, editing and annotation platform leveraging fine-tuned models for "
                 "AI-assisted labelling; published 3 open datasets to Hugging Face (18,000+ downloads)."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2020 – 2022",
            "bullets": [
                ("Built and maintained REST and WebSocket APIs in Django and Node.js serving 1.2M requests/day at p95 "
                 "latency under 140 ms, with PostgreSQL, Redis and Twilio voice/SMS integrations."),
                ("Introduced Docker deployments and a GitHub Actions CI/CD pipeline: release cadence moved from monthly "
                 "to weekly and lead time dropped from 3 weeks to 2 days."),
            ],
        },
    ],
    "projects": [
        ("LabelSet — Speech Data Pipeline", "Sources recordings, gets them labelled by real speakers, and verifies label "
            "quality before training — the data backbone behind every model in the portfolio."),
        ("EchoID — Audio Archive Indexing", "Batch pipeline applying diarisation, voice embeddings and ASR to turn raw "
            "archives into speaker-labelled, searchable transcripts."),
        ("SautiFlow — Script-to-Skit Product", "Turns a written script into a finished skit — casting, voicing, timing "
            "and mix — giving creators ten renderable variations per joke; served end to end by the audio ingestion, "
            "alignment and labelling pipelines described above."),
    ],
    "education": [
        ("BSc, Computer Security and Forensics", "Jaramogi Oginga Odinga University of Science and Technology (JOOUST)", "2016 – 2020"),
        ("Diploma, Mechatronics Engineering", "JKUAT, Juja, Kenya", "2013 – 2016"),
    ],
    "certs": "AWS, Google Cloud, DeepLearning.AI and NVIDIA DLI certifications (2021 – 2025).",
    "extra": None,
}

SOFTWARE_ENGINEER = {
    "file": "LYLE-OKOTH-SOFTWARE-ENGINEER.docx",
    "headline": "SOFTWARE ENGINEER | FULL-STACK & VOICE-FIRST PRODUCTS",
    "summary": (
        "Software Engineer with 6+ years of experience shipping end-to-end web products — from problem framing and "
        "UI/UX design through backend APIs at 1.2M requests/day to deployment and feedback loops. Specialised in "
        "voice-first services: IVR and WhatsApp assistants serving 40,000+ monthly users, real-time speech streaming "
        "front-ends, and AI-assisted onboarding. Introduced Docker-based CI/CD that cut release lead time from 3 weeks "
        "to 2 days, and grew front-end test coverage from 0 to 71%, reducing reported production bugs 34%."
    ),
    "competencies": [
        ("Backend", "REST and WebSocket APIs, synchronous and asynchronous services for real-time streaming and batch "
                    "processing, authentication & authorization, payment webhooks, USSD menus, Twilio voice/SMS"),
        ("Frontend & Product", "React interfaces for speech products (real-time translation, transcription, synthesis), "
                               "UI/UX design, AI-assisted onboarding workflows, documentation that sped up new-hire onboarding"),
        ("Platform & Reliability", "Docker, GitHub Actions CI/CD, Kubernetes, logging and tracing for API-usage "
                                   "monitoring and downtime prevention, bot-abuse mitigation"),
        ("ML Integration", "Serving models behind FastAPI, LLM-powered features (onboarding, pre-labeling), "
                           "RAG and agent workflows with LangChain / LlamaIndex"),
    ],
    "tech": [
        ("Languages", "Python, JavaScript/TypeScript, C++, SQL"),
        ("Frameworks", "Django, FastAPI, Flask, Node.js, React"),
        ("Data & Messaging", "PostgreSQL, Redis, Elasticsearch, Apache Kafka, Celery"),
        ("DevOps & Cloud", "Docker, Kubernetes, GitHub Actions CI/CD, AWS, GCP, Render"),
        ("Other", "Twilio, payment integrations, WebSocket / WebRTC streaming, scikit-learn, Hugging Face"),
    ],
    "jobs": [
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2020 – 2022",
            "bullets": [
                ("Shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ monthly users, "
                 "from requirement framing with non-technical clients through design, build and iteration."),
                ("Built REST and WebSocket APIs in Django and Node.js handling 1.2M requests/day while holding p95 "
                 "latency under 140 ms."),
                ("Introduced Docker deployments and a GitHub Actions CI/CD pipeline: release cadence moved from monthly "
                 "to weekly and lead time dropped from 3 weeks to 2 days."),
                ("Took front-end test coverage from 0 to 71%; reported production bugs fell 34% over two quarters."),
                ("Trained and served the team's first machine-learning model — a scikit-learn intent classifier behind "
                 "FastAPI that deflected 28% of support chats; integrated Twilio voice, SMS, payment webhooks and USSD menus."),
                ("Reviewed junior pull requests and ran the internal weekly code club."),
            ],
        },
        {
            "title": "Machine Learning Engineer (full-stack responsibilities)",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Worked with software engineers to design and ship web interfaces for speech products including "
                 "real-time streaming translation, transcription and synthesis — contributing to high retention rates."),
                ("Deployed model services (FastAPI, Triton, Kubernetes) serving streaming speech at 310 ms median "
                 "first-audio latency; instrumented logging and tracing to monitor token usage and detect model drift."),
                ("Built robust authentication and authorization controls that prevented API misuse by bots, improving "
                 "the experience for real users."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2024",
            "bullets": [
                ("Built a fast, scalable synchronous and asynchronous backend for real-time and batch processing of user "
                 "requests, plus the data studio for human + AI collaborative data collection and annotation."),
                ("Designed pipelines (Airflow, Kafka, Spark) processing 6 TB of audio per year; wrote detailed "
                 "documentation that made onboarding new hires easier."),
            ],
        },
    ],
    "projects": [
        ("SautiFlow — Script-to-Skit Studio", "Turns a written script into a finished skit: casting, voicing, timing and "
            "mix. Creators type the joke, pick a cast, and get back ten renderable variations instead of one take they "
            "have to record themselves — full product surface from web UI to render backend."),
        ("LabelSet — Speech Data Platform", "Web application for sourcing recordings, collaborative human + AI labelling, "
            "and label-quality verification — the pipeline behind every model on the portfolio."),
        ("FaceForm — Persona Generator", "Generates consistent, clearly synthetic faces for teams that need people in "
            "their visuals without licensing real ones; a designer sets an archetype once, then draws a whole persona "
            "family from the same latent noise."),
        ("PigaMagic — Event Photo Gallery", "Takes a few phone snapshots per guest at a 200-person event and returns a "
            "gallery of polished event photos for every guest, not just the ones near the camera."),
    ],
    "education": [
        ("BSc, Computer Security and Forensics", "Jaramogi Oginga Odinga University of Science and Technology (JOOUST)", "2016 – 2020"),
        ("Diploma, Mechatronics Engineering", "JKUAT, Juja, Kenya", "2013 – 2016"),
    ],
    "certs": "AWS, Google Cloud, DeepLearning.AI and NVIDIA DLI certifications (2021 – 2025).",
    "extra": ("LEADERSHIP", ["Co-Founder — SautiFlow Labs (2022)", "Volunteer — OMDENA (2024)",
                             "Founded a 12-member coding club and ran weekend build sessions"]),
}


def build(cv):
    doc = build_doc()
    header(doc, cv["headline"])

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
    for name, desc in cv["projects"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(name + " — ")
        r.bold = True
        r.font.size = Pt(10.5)
        r2 = p.add_run(desc)
        r2.font.size = Pt(10.5)

    section_heading(doc, "Education")
    for title, school, dates in cv["education"]:
        job_header(doc, title, school, dates)

    section_heading(doc, "Certifications")
    para(doc, cv["certs"], space_after=4)

    if cv["extra"]:
        section_heading(doc, cv["extra"][0])
        for item in cv["extra"][1]:
            bullet(doc, item)

    section_heading(doc, "References")
    para(doc, "Available on request.", space_after=0)

    doc.save(cv["file"])
    print("saved", cv["file"])


if __name__ == "__main__":
    for cv in (ML_ENGINEER, DATA_ENGINEER, SOFTWARE_ENGINEER):
        build(cv)
