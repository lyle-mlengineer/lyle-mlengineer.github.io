# Lyle Okoth — experience

## Machine Learning Engineer — SautiFlow Labs, Nairobi (2024 – present)

- Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 on 1,240 hours of in-house audio.
- Shipped streaming speech-to-speech translation at **310 ms median / 780 ms p95 first-audio latency** across six language pairs (English and Swahili, Luo and Kikuyu), down from a 1.4 s batch baseline.
- Compressed a 1.6 GB TTS checkpoint to **480 MB** with int8 quantisation and KV caching: **42 concurrent voices per GPU**, 3.1x throughput and 58% lower inference cost.
- Designed and shipped **12 Kenyan-language voice personas** across Swahili, Sheng, Luo and Kikuyu — persona
  bibles, pronunciation lexicons and MOS panels with native listeners — scoring **4.1/5**.
- Built the agentic podcast pipeline — research, scripting, casting, render, mastering and show-notes agents —
  with a source ledger and human approval gates before anything is published.
- Built the evaluation harness — WER, CER, MOS and CI regression gates — which blocked **9 model regressions** from release in two quarters.
- Published **3 open speech datasets and 2 fine-tuned models** on Hugging Face, with **18,000+ downloads**.
- Grew the studio to **2,100 monthly creators at 61% week-four retention**.

## Data Engineer — SautiFlow Labs, Nairobi (2023 – 2024)

- Designed batch and streaming pipelines (Airflow, Kafka, Spark) processing **6 TB / 38,000 hours** of raw audio a year into training-ready datasets.
- Automated transcription alignment and diarisation pre-labelling, cutting human labelling from **11 to 3.5 minutes per hour of audio** — a 68% saving adopted as the platform default.
- Introduced DVC versioning with content hashing so every model release traces to an exact data snapshot; consolidated 14 schemas into a dbt warehouse, cutting compute spend 23%.
- Designed **LabelSet** across **11 speech task types** — transcription, translation, diarisation, voice design and cloning, speech description, benchmarks and RL environments — with 60-second mono 16 kHz preprocessing, review and JSONL export.

## Software Engineer — SautiFlow Labs, Nairobi (2022 – 2023)

- Shipped 5 production features for an IVR and WhatsApp voice assistant serving **40,000+ monthly users**, with REST and WebSocket APIs in Django and Node.js at p95 latency under 140 ms.
- Introduced Docker deploys and GitHub Actions CI/CD — release cadence monthly to weekly, lead time 3 weeks to 2 days — and took front-end test coverage from 0 to 71%.
- Built REST and WebSocket APIs in Django and Node.js serving **1.2M requests a day at p95 latency under 140 ms**.
- Shipped a scikit-learn intent classifier that deflected **28% of support chats**; reported production bugs fell **34%**.

## Freelance AI Engineer — Independent, remote (2026 – present)

- Built **Suraya**, an audit-driven latent-diffusion pipeline for photoreal Kenyan faces: 889-image data audit, face detect and align, a compact 66M UNet on a frozen SD VAE, and KID-led evaluation.
- Shipped **Vocalis** and **EchoID** with provider-agnostic voice and transcription adapters, credit ledgers and idempotent M-Pesa / Stripe settlement, evaluating provider output before release.
- Wrote the evaluation and guardrail patterns clients keep using: offline quality gates, latency and cost budgets, secret redaction and human approval for sensitive actions.

## Earlier

- Co-Founder — SautiFlow Labs (2022).
- Volunteer — OMDENA (2024).
- Diploma, Mechatronics Engineering (Upper Second Class) — JKUAT (2016 – 2019), before moving into software and data engineering.
