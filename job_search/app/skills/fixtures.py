"""Offline fixture outputs, grounded in data/portfolio.

Used by the fake LLM provider so the real pipeline runs without a key and tests
can assert on deterministic content.
"""

from __future__ import annotations

FAKE_CV: dict = {
    "headline": "SENIOR MACHINE LEARNING ENGINEER | SPEECH & VOICE AI",
    "summary": (
        "Machine Learning Engineer with four years of experience designing, training and productionising "
        "multilingual speech and vision systems — ASR, speech-to-speech translation, TTS and diffusion image "
        "models — for East African languages. Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8%, "
        "shipped streaming translation at 310 ms median first-audio latency, and raised TTS capacity to 42 "
        "concurrent voices per GPU. Owns the evaluation gates that keep regressions out of release."
    ),
    "skill_groups": [
        {
            "name": "Speech & Voice AI",
            "items": [
                "ASR (Whisper, wav2vec 2.0, NeMo)",
                "TTS and voice design (VITS, XTTS-v2, Fish Audio, Breeze)",
                "Speech-to-speech translation (SeamlessM4T, NLLB-200)",
                "Diarisation and VAD",
            ],
        },
        {
            "name": "Modelling & Evaluation",
            "items": [
                "PyTorch training and distributed runs",
                "LoRA / QLoRA fine-tuning",
                "WER / CER / MOS evaluation",
                "KID / FID and blind listening panels",
            ],
        },
        {
            "name": "MLOps & Serving",
            "items": [
                "int8 / FP16 / NF4 quantisation",
                "ONNX Runtime, TensorRT, Triton Inference Server, vLLM",
                "KV caching and continuous batching",
                "CI regression gates, Docker, Kubernetes",
            ],
        },
        {
            "name": "Data & Tooling",
            "items": [
                "Python, C++, JavaScript/TypeScript, SQL",
                "Apache Spark, Kafka, Airflow, dbt",
                "DVC, Great Expectations, Weights & Biases, MLflow",
                "PostgreSQL, Redis, FastAPI",
            ],
        },
    ],
    "experience": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                "Built Suraya, an audit-driven latent-diffusion pipeline for photoreal Kenyan faces: 889-image "
                "data audit, face detect and align, a compact 66M UNet on a frozen SD VAE, and KID-led evaluation.",
                "Shipped Vocalis and EchoID with provider-agnostic voice and transcription adapters, credit "
                "ledgers and idempotent M-Pesa / Stripe settlement, evaluating provider output before release.",
                "Wrote the evaluation and guardrail patterns clients keep using: offline quality gates, latency "
                "and cost budgets, secret redaction and human approval for sensitive actions.",
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                "Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning "
                "Whisper-large-v3 on 1,240 hours of in-house audio.",
                "Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio "
                "latency across six language pairs (English and Swahili, Luo and Kikuyu), down from a 1.4 s "
                "batch baseline.",
                "Compressed a 1.6 GB TTS checkpoint to 480 MB with int8 quantisation and KV caching: 42 "
                "concurrent voices per GPU, 3.1x throughput and 58% lower inference cost.",
                "Built the evaluation harness — WER, CER, MOS and CI regression gates — which blocked 9 model "
                "regressions from release in two quarters.",
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                "Designed batch and streaming pipelines (Airflow, Kafka, Spark) processing 6 TB / 38,000 hours "
                "of raw audio a year into training-ready datasets.",
                "Automated transcription alignment and diarisation pre-labelling, cutting human labelling from "
                "11 to 3.5 minutes per hour of audio — a 68% saving adopted as the platform default.",
                "Introduced DVC versioning with content hashing so every model release traces to an exact data "
                "snapshot; consolidated 14 schemas into a dbt warehouse, cutting compute spend 23%.",
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                "Shipped 5 production features for an IVR and WhatsApp voice assistant serving 40,000+ monthly "
                "users, with REST and WebSocket APIs in Django and Node.js at p95 latency under 140 ms.",
                "Introduced Docker deploys and GitHub Actions CI/CD — release cadence monthly to weekly, lead "
                "time 3 weeks to 2 days — and took front-end test coverage from 0 to 71%.",
            ],
        },
    ],
    "projects": [
        {
            "name": "Vocalis — Voice Design Studio",
            "meta": "FastAPI, Jinja2, provider adapters",
            "bullets": [
                "Brief-to-voice studio with design, audition, album and narration flows across provider-agnostic "
                "Breeze and Fish Audio adapters.",
                "Credit ledger with idempotent M-Pesa and Stripe settlement and a FastAPI + Jinja2 monolith.",
            ],
        },
        {
            "name": "EchoID — Speaker-Aware Transcription Studio",
            "meta": "FastAPI, diarisation, billing",
            "bullets": [
                "Upload → diarise → review → export with speaker-labelled transcripts, reusable profiles and "
                "JSON, TXT or branded PDF exports.",
                "A pluggable transcription provider behind one JSON contract, credit billing and a domain-driven "
                "FastAPI monolith.",
            ],
        },
        {
            "name": "Suraya — Diffusion Model for Kenyan Faces",
            "meta": "PyTorch, latent diffusion",
            "bullets": [
                "Audit-driven latent diffusion model with face detect and align, a VAE quality gate and "
                "KID-led evaluation.",
                "Compact 66M-parameter UNet on a frozen SD VAE, with an SDXL LoRA track for comparison.",
            ],
        },
    ],
    "education": [
        {
            "credential": "BSc, Computer Security and Forensics (in progress)",
            "institution": "JOOUST",
            "dates": "2024 – 2028",
        },
        {
            "credential": "Diploma, Mechatronics Engineering (Upper Second Class)",
            "institution": "JKUAT, Juja, Kenya",
            "dates": "2016 – 2019",
        },
    ],
    "certifications": (
        "DeepLearning.AI, NVIDIA Deep Learning Institute, AWS and Google Cloud — 14 credentials (2021 – 2025)."
    ),
}
