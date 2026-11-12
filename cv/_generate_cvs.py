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

    links = doc.add_paragraph()
    links.alignment = WD_ALIGN_PARAGRAPH.CENTER
    links.paragraph_format.space_after = Pt(2)
    for i, (label, url) in enumerate(LINKS):
        if i:
            sep = links.add_run("  |  ")
            sep.font.size = Pt(10)
        add_hyperlink(links, url, label, size=10)


ML_ENGINEER = {
    "file": "LYLE-OKOTH-MACHINE-LEARNING-ENGINEER.docx",
    "headline": "MACHINE LEARNING ENGINEER | SPEECH & VOICE AI",
    "summary": (
        "Machine Learning Engineer and researcher with over six years of experience designing, training and "
        "productionising multilingual speech systems — automatic speech recognition, speech-to-speech translation "
        "and text-to-speech synthesis — for East African languages. Owns the full model lifecycle from data and "
        "evaluation to deployment: cut Swahili and Sheng ASR error rate from 23.4% to 11.8%, shipped streaming "
        "speech translation at 310 ms median first-audio latency across six language pairs, and raised capacity to "
        "42 concurrent voices per GPU while cutting inference cost 58%. Published three open speech datasets and "
        "two fine-tuned models on Hugging Face with 18,000+ downloads."
    ),
    "competencies": [
        ("Speech & Voice AI", "ASR (Whisper, wav2vec 2.0, NeMo), TTS and voice cloning (VITS, XTTS-v2, Coqui, "
                              "F5-TTS), speech-to-speech translation (SeamlessM4T, NLLB-200), diarisation, VAD and "
                              "speaker embeddings (pyannote.audio)"),
        ("Modelling & Evaluation", "PyTorch training and distributed runs, LoRA / QLoRA fine-tuning, diffusion and "
                                   "flow-matching models, WER / CER / MOS evaluation, blind listening tests, experiment "
                                   "tracking (Weights & Biases, MLflow, Optuna)"),
        ("MLOps & Serving", "int8 / FP16 quantisation, ONNX Runtime, TensorRT, Triton Inference Server, vLLM, KV "
                            "caching, continuous batching, CI regression gates, Kubernetes, Grafana monitoring"),
        ("Research & Product", "Research-to-production, multilingual and low-resource speech, annotation platforms, "
                               "technical writing, product design for voice interfaces"),
    ],
    "tech": [
        ("Languages", "Python, C++, JavaScript/TypeScript, SQL"),
        ("Speech & ML", "PyTorch 2.x, Hugging Face Transformers, PEFT, Accelerate, DeepSpeed, Diffusers, ESPnet, "
                        "Coqui TTS, pyannote.audio, scikit-learn, Optuna"),
        ("Serving & Infra", "FastAPI, Triton Inference Server, ONNX Runtime, TensorRT, vLLM, gRPC / WebSocket "
                            "streaming, WebRTC, Redis, Celery, Docker, Kubernetes"),
        ("Data & MLOps", "Apache Spark, Kafka, Airflow, dbt, DVC, Great Expectations, Weights & Biases, MLflow, "
                         "Terraform"),
        ("Cloud", "AWS (S3, GPU instances), Google Cloud, Render"),
    ],
    "jobs": [
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 hours of in-house audio."),
                ("Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs (English ↔ Swahili, Luo and Kikuyu), down from a 1.4 s batch baseline; "
                 "domain fine-tuning added 1.9 chrF over the open model."),
                ("Compressed a 1.6 GB TTS checkpoint to 480 MB with int8 quantisation and KV caching: 42 concurrent "
                 "voices per GPU, 3.1x throughput and 58% lower inference cost."),
                ("Built the evaluation harness — WER, CER, MOS and CI regression gates — which blocked 9 model "
                 "regressions from release in two quarters."),
                ("Built diarisation, VAD and speaker-embedding pipelines for multi-speaker meeting audio: 89% speaker "
                 "accuracy on up to 8 speakers at a 12.4% diarisation error rate."),
                ("Published 3 open speech datasets and 2 fine-tuned models to Hugging Face (18,000+ downloads in the "
                 "first quarter) and set the team's model-card and experiment-tracking standard across 60+ runs a month."),
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
                 "3.5 minutes per hour of audio — a 68% saving adopted as the platform's default workflow."),
                ("Introduced dataset versioning with DVC and content hashing, so every model release traces to an exact "
                 "data snapshot."),
                ("Consolidated 14 scattered schemas into one dbt-modelled warehouse: pipeline failures down 41%, monthly "
                 "compute spend down 23%."),
                ("Owned speaker consent, retention and PII-redaction flows for 40,000+ hours of stored audio."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ monthly users."),
                ("Built REST and WebSocket APIs in Django and Node.js handling 1.2M requests a day at p95 latency under "
                 "140 ms."),
                ("Introduced Docker deploys and GitHub Actions CI/CD: release cadence from monthly to weekly, lead time "
                 "from 3 weeks to 2 days."),
                ("Took front-end test coverage from 0 to 71% and reduced reported production bugs 34%; trained the "
                 "team's first model, a scikit-learn intent classifier that deflected 28% of support chats."),
            ],
        },
    ],
    "projects": [
        ("Vocalis — Brand Voice Studio",
         "Voice-cloning TTS studio: one licensed studio read in, a reusable brand voice out, served over a streaming "
         "API in 32 languages — 42 concurrent voices per GPU, 6 working days from recordings to a deployed voice.",
         [("github.com/lyle-mlengineer/vocalis", "https://github.com/lyle-mlengineer/vocalis"),
          ("vocalis-rvcw.onrender.com", "https://vocalis-rvcw.onrender.com")]),
        ("EchoID — Speaker Identification & Diarisation",
         "Turns raw recordings into speaker-labelled, searchable transcripts. 89% speaker accuracy on meetings with "
         "up to 8 speakers at a 12.4% diarisation error rate; one hour of four-speaker audio processed in 4 minutes "
         "on a single GPU.",
         [("github.com/lyle-mlengineer/echoid", "https://github.com/lyle-mlengineer/echoid"),
          ("echoid.onrender.com", "https://echoid.onrender.com")]),
        ("LabelSet — Speech & Multimodal Data Platform",
         "Sources recordings, gets them labelled by real speakers and proves the labels are trustworthy before a "
         "training run. 18,000 hours of audio and 1.2M images delivered across 11 language and accent bands at "
         "Cohen's kappa 0.87.",
         [("labelset.onrender.com", "https://labelset.onrender.com")]),
        ("FaceForm — Synthetic Persona Generator",
         "Consistent, clearly synthetic faces drawn from one latent neighbourhood. 96% of released sets passed human "
         "realism review, and persona sets ship 8x faster than the stock-photography workflow they replaced.",
         [("github.com/lyle-mlengineer/faceform", "https://github.com/lyle-mlengineer/faceform"),
          ("faceform-2rkf.onrender.com", "https://faceform-2rkf.onrender.com")]),
    ],
    "education": [
        ("BSc, Computer Security and Forensics (First Class Honours)", "Jaramogi Oginga Odinga University of Science and Technology (JOOUST)", "2016 – 2020"),
        ("Diploma, Mechatronics Engineering (Upper Second Class)", "JKUAT, Juja, Kenya", "2013 – 2016"),
    ],
    "certs": "DeepLearning.AI, NVIDIA Deep Learning Institute, AWS and Google Cloud — 14 credentials (2021 – 2025).",
    "extra": None,
}

DATA_ENGINEER = {
    "file": "LYLE-OKOTH-DATA-ENGINEER.docx",
    "headline": "DATA ENGINEER | AUDIO & MULTIMODAL ML DATA",
    "summary": (
        "Data Engineer with over six years of experience building the ingestion, alignment, labelling and versioning "
        "path that turns raw audio and images into training-ready datasets. Delivered 6 TB / 38,000 hours of raw "
        "audio a year, cut manual labelling time 68%, and reduced pipeline failures 41% by consolidating 14 schemas "
        "into a dbt-modelled warehouse. Owns data quality, consent, retention and PII redaction for 40,000+ hours of "
        "stored audio, with the software background (APIs at 1.2M requests a day) to keep pipelines operable in "
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
        ("Platform & Reliability", "AWS S3, GCS, PostgreSQL, BigQuery, Elasticsearch, Redis, Terraform, Docker, "
                                   "Kubernetes, on-call observability: monthly restores replaced by daily automated checks"),
    ],
    "tech": [
        ("Languages", "Python, SQL, JavaScript/TypeScript, C++"),
        ("Processing", "Apache Spark, Kafka, Airflow, dbt, DuckDB, Polars / Pandas, Celery"),
        ("Storage & Warehousing", "PostgreSQL, BigQuery, AWS S3, GCS, Parquet / Arrow, Delta Lake, Elasticsearch, Redis"),
        ("Quality & Versioning", "Great Expectations, DVC, data contracts, dataset cards and lineage"),
        ("Infrastructure", "Docker, Kubernetes, Terraform, GitHub Actions CI/CD, AWS, GCP, Render"),
    ],
    "jobs": [
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
                ("Consolidated 14 scattered schemas into a single dbt-modelled warehouse, reducing pipeline failures 41% "
                 "and monthly compute spend 23%."),
                ("Delivered 18,000 hours of audio and 1.2M images across 11 language and accent bands at Cohen's kappa "
                 "0.87, cutting batch turnaround from 3.5 weeks to 9 days."),
                ("Owned speaker consent, retention and PII-redaction flows for 40,000+ hours of stored audio; wrote the "
                 "data-quality runbook that onboarded 3 team members."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Built and maintained REST and WebSocket APIs in Django and Node.js serving 1.2M requests a day at p95 "
                 "latency under 140 ms, with PostgreSQL, Redis and Twilio voice/SMS integrations."),
                ("Introduced Docker deployments and a GitHub Actions CI/CD pipeline: release cadence moved from monthly "
                 "to weekly and lead time dropped from 3 weeks to 2 days."),
            ],
        },
    ],
    "projects": [
        ("LabelSet — Speech & Multimodal Data Platform",
         "Sources audio, image and video data, routes each task to three annotators with adjudication, and ships "
         "versioned datasets with a dataset card per release. 18,000 hours of audio and 1.2M images delivered at "
         "Cohen's kappa 0.87, with turnaround cut from 3.5 weeks to 9 days.",
         [("labelset.onrender.com", "https://labelset.onrender.com")]),
        ("EchoID — Audio Archive Indexing",
         "Indexes raw recordings into speaker-labelled, searchable transcripts with Elasticsearch, word-level ASR "
         "timestamps and a redaction pass that masks phone numbers, IDs and card fragments before anything leaves "
         "the pipeline. 40,000 hours indexed for production tenants.",
         [("github.com/lyle-mlengineer/echoid", "https://github.com/lyle-mlengineer/echoid"),
          ("echoid.onrender.com", "https://echoid.onrender.com")]),
        ("SautiFlow — Script-to-Skit Product",
         "Turns a written script into a finished skit — casting, voicing, timing and mix — served end to end by the "
         "audio ingestion, alignment and labelling pipelines described above. 40+ skits per creator per session and "
         "a median 22-second render for a 45-second, four-character scene.",
         [("sautiflow.co.ke", "https://www.sautiflow.co.ke/")]),
    ],
    "education": [
        ("BSc, Computer Security and Forensics (First Class Honours)", "Jaramogi Oginga Odinga University of Science and Technology (JOOUST)", "2016 – 2020"),
        ("Diploma, Mechatronics Engineering (Upper Second Class)", "JKUAT, Juja, Kenya", "2013 – 2016"),
    ],
    "certs": "DeepLearning.AI, NVIDIA Deep Learning Institute, AWS and Google Cloud — 14 credentials (2021 – 2025).",
    "extra": None,
}

SOFTWARE_ENGINEER = {
    "file": "LYLE-OKOTH-SOFTWARE-ENGINEER.docx",
    "headline": "SOFTWARE ENGINEER | FULL-STACK & VOICE-FIRST PRODUCTS",
    "summary": (
        "Software Engineer with over six years of experience shipping voice-first web products end to end — "
        "requirement framing, UI/UX, backend APIs, deployment and iteration. Built IVR and WhatsApp assistants "
        "serving 40,000+ monthly users, REST and WebSocket APIs handling 1.2M requests a day at p95 latency under "
        "140 ms, and Docker + GitHub Actions CI/CD that moved releases from monthly to weekly and cut lead time from "
        "3 weeks to 2 days. Took front-end test coverage from 0 to 71% while reported production bugs fell 34%; now "
        "ships streaming speech interfaces and model services at 310 ms median first-audio latency."
    ),
    "competencies": [
        ("Backend", "REST and WebSocket APIs, Django / FastAPI / Node.js, authentication and authorisation, payment "
                    "webhooks, USSD menus, Twilio voice and SMS, real-time streaming services"),
        ("Frontend & Product", "React interfaces for speech products (streaming translation, transcription and "
                               "synthesis), UI/UX design, AI-assisted onboarding workflows, documentation that sped up "
                               "new-hire onboarding"),
        ("Platform & Reliability", "Docker, GitHub Actions CI/CD, Kubernetes, Render deployments, logging, tracing "
                                   "and cost monitoring, bot-abuse mitigation"),
        ("ML Integration", "Model services behind FastAPI and Triton, LLM-powered features (onboarding, pre-labelling), "
                           "RAG and agent workflows"),
    ],
    "tech": [
        ("Languages", "Python, JavaScript/TypeScript, C++, SQL"),
        ("Frameworks", "Django, FastAPI, Flask, Node.js, React, Next.js"),
        ("Data & Messaging", "PostgreSQL, Redis, Elasticsearch, Apache Kafka, Celery"),
        ("DevOps & Cloud", "Docker, Kubernetes, GitHub Actions CI/CD, Render, AWS, GCP"),
        ("Other", "Twilio, payment integrations, WebSocket / WebRTC streaming, scikit-learn, Hugging Face, Triton"),
    ],
    "jobs": [
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
    ],
    "projects": [
        ("SautiFlow — Script-to-Skit Studio",
         "Turns a written script into a finished skit — casting, voicing, timing and mix — where creators type the joke, "
         "pick a cast and get ten renderable variations instead of one take they have to record themselves. Full "
         "product surface from web UI to render backend; 2,100 monthly creators at 61% week-four retention and a "
         "median 22-second render for a 45-second four-character scene.",
         [("sautiflow.co.ke", "https://www.sautiflow.co.ke/")]),
        ("LabelSet — Speech & Multimodal Data Platform",
         "Web application where audio, image and video tasks route to three annotators with adjudication before a "
         "versioned dataset ships. 18,000 hours of audio and 1.2M images delivered at Cohen's kappa 0.87, with "
         "turnaround cut from 3.5 weeks to 9 days.",
         [("labelset.onrender.com", "https://labelset.onrender.com")]),
        ("FaceForm — Persona Generator",
         "Generates consistent, clearly synthetic faces for teams that need people in their visuals without licensing "
         "real ones: a designer sets an archetype once, then draws a whole persona family from the same latent noise. "
         "96% of released sets passed an internal human realism check, 8x faster than the stock-and-permission "
         "workflow it replaced, with 31,000 licensed images generated in year one.",
         [("github.com/lyle-mlengineer/faceform", "https://github.com/lyle-mlengineer/faceform"),
          ("faceform-2rkf.onrender.com", "https://faceform-2rkf.onrender.com")]),
        ("PigaMagic — Event Photo Gallery",
         "Takes a few phone snapshots per guest at a 200-person event and returns a polished gallery for every guest, "
         "not just the ones near the camera: 12 gallery shots per guest in under four minutes from upload, with 94% "
         "passing the automated identity-similarity check and 1 in 6 generations rejected at the quality gate.",
         [("pigamagic.onrender.com", "https://pigamagic.onrender.com")]),
    ],
    "education": [
        ("BSc, Computer Security and Forensics (First Class Honours)", "Jaramogi Oginga Odinga University of Science and Technology (JOOUST)", "2016 – 2020"),
        ("Diploma, Mechatronics Engineering (Upper Second Class)", "JKUAT, Juja, Kenya", "2013 – 2016"),
    ],
    "certs": "AWS, Google Cloud, DeepLearning.AI and NVIDIA DLI certifications — 14 credentials (2021 – 2025).",
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

    refs = para(doc, "References available on request.", size=9.5, space_after=0, italic=True)
    refs.paragraph_format.space_before = Pt(6)

    doc.save(cv["file"])
    print("saved", cv["file"])


if __name__ == "__main__":
    for cv in (ML_ENGINEER, DATA_ENGINEER, SOFTWARE_ENGINEER):
        build(cv)
