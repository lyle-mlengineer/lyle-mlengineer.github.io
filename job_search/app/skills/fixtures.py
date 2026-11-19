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

FAKE_RESEARCH = {
    "summary": (
        "Acme Speech builds multilingual voice interfaces for customer support teams. Its public "
        "engineering writing focuses on speech recognition quality, low-latency streaming and evaluation."
    ),
    "industry": "Voice AI and customer support software",
    "size": "51–200",
    "founded": "",
    "hq": "Remote-first, Europe",
    "products": [
        "Real-time speech recognition for support calls",
        "Multilingual voice agents",
    ],
    "tech_stack": ["Python", "PyTorch", "Whisper", "Kubernetes"],
    "culture": [
        "Public engineering notes emphasise evaluation before optimisation.",
        "Remote-first with written design reviews.",
    ],
    "news": [],
    "interview_style": "A practical screen on speech evaluation, then a systems discussion and a team interview.",
    "talking_points": [
        "The posting's evaluation focus matches the harness that blocked model regressions at SautiFlow.",
        "Whisper fine-tuning and quantisation work map directly to the stated stack.",
    ],
    "open_questions": [
        "Which languages are in scope for the first year?",
        "How is on-call shared across the ML team?",
    ],
    "sources": [
        {"title": "Acme Speech — about", "url": "https://acme.example/about", "grade": "page"},
        {"title": "Acme Speech engineering", "url": "https://acme.example/engineering", "grade": "page"},
        {"title": "Acme Speech news", "url": "https://acme.example/news", "grade": "snippet"},
    ],
}

FAKE_COVER = {
    "greeting": "Dear Acme Speech team,",
    "paragraphs": [
        (
            "I am applying for the Senior Machine Learning Engineer role. I build multilingual speech "
            "systems and the evaluation infrastructure that keeps them honest. At SautiFlow Labs I cut "
            "Swahili and Sheng ASR word error rate from 23.4% to 11.8% by fine-tuning Whisper-large-v3 on "
            "1,240 hours of in-house audio, then shipped streaming speech-to-speech translation at 310 ms "
            "median first-audio latency."
        ),
        (
            "Your posting puts recognition quality and evaluation tooling at the centre of the role, which "
            "is the work I keep returning to. I built the WER, CER and MOS harness and CI regression gates "
            "that blocked nine model regressions from release in two quarters. I also compressed a 1.6 GB "
            "TTS checkpoint to 480 MB with int8 quantisation and KV caching, reaching 42 concurrent voices "
            "per GPU."
        ),
        (
            "I would bring the same balance to Acme Speech: careful measurement first, then the serving work "
            "that makes a model cheap enough to ship. I would welcome the chance to discuss how your team "
            "evaluates new languages and model changes."
        ),
    ],
    "closing": "Sincerely,",
}

FAKE_EMAIL = {
    "subject": "Application — Senior Machine Learning Engineer",
    "body": (
        "Hello Acme Speech team,\n\nI have applied for the Senior Machine Learning Engineer role and "
        "attached my CV and cover letter. I have spent four years on multilingual speech systems, "
        "including a Whisper fine-tune that cut Swahili and Sheng word error rate from 23.4% to 11.8%, "
        "and the evaluation harness that kept regressions out of release.\n\nYour focus on recognition "
        "quality and streaming latency is exactly the work I want to do next. I would be glad to talk "
        "through how I would approach evaluation across your languages.\n\nThank you for your time.\n\n"
        "Lyle Okoth"
    ),
    "attachment_names": ["CV", "Cover letter"],
}

FAKE_TELL = {
    "answer": (
        "I am a machine learning engineer based in Nairobi, focused on multilingual speech and audio. "
        "I started in software and data engineering, which is why I tend to own the whole path from raw "
        "audio to a model in production rather than only the training notebook.\n\n"
        "At SautiFlow Labs I cut "
        "Swahili and Sheng ASR word error rate from 23.4% to 11.8% by fine-tuning Whisper-large-v3 on "
        "1,240 hours of in-house audio. I also shipped streaming speech-to-speech translation at 310 ms "
        "median first-audio latency and compressed a TTS checkpoint to 480 MB, reaching 42 concurrent "
        "voices per GPU.\n\n"
        "The part I care most about is evaluation: I built the WER, CER and MOS harness "
        "and CI gates that blocked nine regressions from release. Outside work I build small products "
        "like Suraya, a diffusion model for Kenyan faces, and Vocalis, a voice design studio. I am "
        "looking for a role where speech quality and serving economics both matter, which is why this "
        "position stood out."
    ),
    "delivery_notes": [
        "Lead with the current role, then the two metrics that fit the posting.",
        "Pause after the evaluation sentence; it is the bridge to their must-haves.",
        "Keep the side projects to one sentence unless asked.",
    ],
    "anchor_points": [
        "Whisper fine-tuning: 23.4% to 11.8% WER on 1,240 hours.",
        "Streaming translation at 310 ms median first-audio latency.",
        "Evaluation harness and CI gates blocked nine regressions.",
    ],
}

FAKE_WORK = {
    "answer": (
        "I moved into machine learning through data engineering. I joined SautiFlow Labs as a software "
        "engineer in 2022, building voice assistant APIs, then moved into data engineering in 2023. There "
        "I built batch and streaming pipelines processing 6 TB and 38,000 hours of audio a year, and "
        "automated alignment and diarisation pre-labelling so human labelling fell from 11 to 3.5 minutes "
        "per hour of audio.\n\n"
        "That work led to my current ML role in 2024, where I own speech recognition "
        "quality. I fine-tuned Whisper-large-v3 and cut Swahili and Sheng WER from 23.4% to 11.8%, shipped "
        "streaming translation at 310 ms median latency, and built the evaluation harness that blocked nine "
        "regressions.\n\n"
        "Since 2026 I have also worked independently on Suraya, Vocalis and EchoID, which "
        "taught me to keep provider adapters, billing and evaluation honest in products people actually "
        "use. The thread is consistent: make the data trustworthy, measure the model, then make it cheap "
        "enough to serve."
    ),
    "timeline": [
        {
            "company": "Independent",
            "role": "Freelance AI Engineer",
            "years": "2026 – Present",
            "proof": "Shipped Suraya, Vocalis and EchoID with evaluation gates and idempotent payments.",
        },
        {
            "company": "SautiFlow Labs",
            "role": "Machine Learning Engineer",
            "years": "2024 – Present",
            "proof": "Cut WER from 23.4% to 11.8% and shipped streaming translation at 310 ms.",
        },
        {
            "company": "SautiFlow Labs",
            "role": "Data Engineer",
            "years": "2023 – 2024",
            "proof": "Processed 6 TB of audio a year and cut labelling from 11 to 3.5 minutes per hour.",
        },
        {
            "company": "SautiFlow Labs",
            "role": "Software Engineer",
            "years": "2022 – 2023",
            "proof": "Built voice assistant APIs serving 40,000+ monthly users.",
        },
    ],
    "delivery_notes": [
        "Keep this to ninety seconds; the timeline is the handout, not the script.",
        "Name the move from software to data to ML as a deliberate progression.",
        "Stop after the current role unless they ask for detail on earlier work.",
    ],
}

FAKE_PROUD = {
    "answer": (
        "The project I am most proud of is the evaluation harness I built at SautiFlow Labs. Before it, "
        "model changes were judged by spot checks, and regressions reached release because nobody could "
        "compare runs consistently. I designed one harness across five ASR models that measured WER, CER "
        "and MOS, ran on a single GPU, and produced a release decision instead of a dashboard nobody read. "
        "I wired it into CI so a regression blocked the build.\n\n"
        "In two quarters it stopped nine model "
        "regressions from release. That mattered more than any single model improvement because it changed "
        "how the team decided what was good enough. The work also forced me to make evaluation fast: an "
        "hour of four-speaker audio is processed in four minutes, and 40,000 hours are indexed for "
        "production tenants.\n\n"
        "I would bring the same approach to Acme Speech: agree the metric, automate the "
        "comparison, then make the gate part of the release path rather than a report someone reads later."
    ),
    "projects": [
        {
            "name": "SautiFlow evaluation harness",
            "why": "It changed release decisions, not just model scores.",
            "what_i_built": "One harness across five ASR models measuring WER, CER and MOS, with CI gates.",
            "impact": "Blocked nine model regressions from release in two quarters.",
            "stack": ["Python", "PyTorch", "Whisper", "CI"],
        },
        {
            "name": "Suraya",
            "why": "It applies the same evaluation discipline to image generation.",
            "what_i_built": "An audit-driven latent diffusion pipeline with face alignment and a VAE quality gate.",
            "impact": "A reproducible 889-image dataset and KID-led evaluation.",
            "stack": ["PyTorch", "Diffusers", "Python"],
        },
    ],
    "delivery_notes": [
        "Tell the before/after: spot checks versus a release gate.",
        "The nine regressions are the proof; do not add invented impact.",
        "Offer the Suraya example only if they ask about vision.",
    ],
}

_TECH_ROWS = [
    ("ASR evaluation", "warm-up", "How do you decide whether a speech model is ready to ship?",
     "I start with the metric that matches the product: WER and CER for transcription, MOS for synthesis, plus latency and cost. At SautiFlow I built one harness across five ASR models and wired it into CI, so a change had to beat the baseline before release. In two quarters that gate blocked nine regressions.", ["Which slices would you report separately?", "How do you stop the test set leaking?"]),
    ("Whisper fine-tuning", "core", "Walk me through fine-tuning Whisper for a new language.",
     "I would audit and normalise the audio first, hold out speaker-disjoint evaluation data, then LoRA-tune Whisper-large-v3 with a learning-rate sweep. At SautiFlow that work cut Swahili and Sheng WER from 23.4% to 11.8% on 1,240 hours. I track WER by language and by speaker group, not just the aggregate.", ["Why LoRA instead of full fine-tuning?", "How do you handle code-switching?"]),
    ("Streaming latency", "core", "How would you hit sub-500 ms first-audio latency?",
     "Stream in small chunks, keep the encoder warm, and measure the whole path rather than the model alone. I shipped speech-to-speech translation at 310 ms median and 780 ms p95 first-audio latency, down from a 1.4 s batch baseline. The gains came from chunking, KV caching and removing synchronous hops outside the model.", ["Where does p95 usually blow up?", "How do you test latency regressions?"]),
    ("Quantisation", "core", "When is int8 quantisation safe for a TTS model?",
     "Only after listening tests show the quality drop is acceptable. I compressed a 1.6 GB checkpoint to 480 MB with int8 quantisation and KV caching, which reached 42 concurrent voices per GPU and 58% lower inference cost. I would compare MOS and blind preference before and after, not just file size.", ["What breaks first after quantisation?", "How do you roll back?"]),
    ("Evaluation data", "core", "How do you build a trustworthy speech evaluation set?",
     "Speaker-disjoint, consented, and stratified by language, accent and recording condition. I would keep a locked test set, version it with content hashes, and report per-slice results. At SautiFlow the data work included alignment and diarisation pre-labelling, which cut human labelling from 11 to 3.5 minutes per hour.", ["How large should the set be?", "How do you detect drift?"]),
    ("PyTorch training", "core", "How do you debug a training run that stops improving?",
     "I check the data pipeline before the model: label alignment, augmentation, and whether the validation split is honest. Then I inspect loss curves, learning rate and gradient norms, and run a small overfit test. Experiment tracking makes the comparison cheap instead of anecdotal.", ["What would you log?", "When do you stop a run?"]),
    ("Serving", "core", "Design the serving path for a multilingual ASR API.",
     "A FastAPI front door, a queue for long audio, and a Triton or vLLM worker with continuous batching. I would stream partial transcripts over WebSocket, cap upload size, and keep a per-language model registry. The SautiFlow streaming service ran at 310 ms median first-audio latency with logging around token use and drift.", ["How do you isolate a bad language model?", "Where would you cache?"]),
    ("Data pipelines", "warm-up", "What does a good audio data pipeline look like?",
     "Idempotent ingestion, schema checks, content hashing and a reproducible dataset version. At SautiFlow I built batch and streaming pipelines processing 6 TB and 38,000 hours of audio a year, and DVC versioning tied every release to an exact snapshot. Bad audio should fail loudly before it reaches training.", ["What do you do with corrupt files?", "How do you handle PII?"]),
    ("Experiment design", "core", "How do you compare two model changes fairly?",
     "Fix the data and evaluation harness, change one variable, and pre-register the metric and slices. I would run both models on the same locked set and report confidence, not a single average. The CI gate at SautiFlow made this the default rather than a special project.", ["What if the gain is only on one slice?", "How do you handle noisy human ratings?"]),
    ("Failure modes", "deep", "What is the most dangerous failure in a speech product?",
     "A confident transcript that is wrong in a way the user cannot detect, especially for names, numbers or a low-resource language. That is why I report per-slice WER and keep a human review path for sensitive content. Evaluation should surface uncertainty, not hide it behind one aggregate score.", ["How would you detect it in production?", "What would you log?"]),
    ("LLM integration", "core", "How do you keep an LLM feature grounded?",
     "Retrieve the source, wrap it as untrusted data, require citations, and check numeric claims mechanically. In Skipper I compare every number in generated prose with the portfolio corpus and rewrite unsupported ones. The same pattern applies to customer-facing summaries: no source, no claim.", ["How do you test prompt injection?", "When do you use a smaller model?"]),
    ("Cost control", "deep", "How do you make a speech product cheap enough to run?",
     "Measure cost per request first, then attack the biggest term: model size, batching, cache hits or audio duration. I used int8, KV caching and continuous batching to reach 42 concurrent voices per GPU at 58% lower inference cost. I would keep a budget alarm and a quality gate so savings never silently degrade output.", ["What is your unit economics model?", "When would you use a smaller model?"]),
]
FAKE_TECH = {
    "questions": [
        {
            "topic": topic,
            "difficulty": difficulty,
            "question": question,
            "answer": answer,
            "follow_ups": follow_ups,
            "grounded_in": "Portfolio: SautiFlow Labs and personal projects",
        }
        for topic, difficulty, question, answer, follow_ups in _TECH_ROWS
    ]
}
FAKE_BEHAVIORAL = {
    "questions": [
        {
            "competency": "Ownership",
            "question": "Tell me about a time you owned a quality problem end to end.",
            "star": {
                "situation": "Model changes at SautiFlow were reaching release on inconsistent spot checks.",
                "task": "I owned the evaluation path and had to make release decisions defensible.",
                "action": "I built one harness across five ASR models with WER, CER and MOS, then wired it into CI as a gate.",
                "result": "The gate blocked nine model regressions from release in two quarters.",
            },
            "answer": "At SautiFlow, model changes were judged by spot checks and regressions sometimes reached release. I owned the evaluation path, built one harness across five ASR models, and wired it into CI. In two quarters it blocked nine regressions. The important shift was that quality became a release condition, not a report.",
        },
        {
            "competency": "Ambiguity",
            "question": "Describe a project where the requirements were unclear.",
            "star": {
                "situation": "Suraya began as a broad idea about Kenyan face generation with no fixed evaluation.",
                "task": "I needed a pipeline that could be judged, not just demonstrated.",
                "action": "I ran an 889-image data audit, defined face alignment and a VAE quality gate, and chose KID-led evaluation.",
                "result": "The pipeline became reproducible and testable before any long training run.",
            },
            "answer": "Suraya started as a broad idea with no fixed evaluation. I made it concrete by auditing 889 images, defining alignment and a VAE quality gate, and choosing KID-led evaluation. That let us judge the pipeline before spending on training, and gave every later change a baseline.",
        },
        {
            "competency": "Communication",
            "question": "Tell me about explaining a technical trade-off to a non-technical audience.",
            "star": {
                "situation": "Stakeholders wanted lower speech latency without understanding the quality cost.",
                "task": "I had to make the trade-off explicit and give them a decision they could own.",
                "action": "I showed latency and WER side by side on the same calls and proposed a p95 target rather than an average.",
                "result": "The team agreed a measured target, and streaming shipped at 310 ms median first-audio latency.",
            },
            "answer": "When stakeholders asked for lower latency, I showed latency and WER side by side on the same calls, then proposed a p95 target instead of an average. That made the quality cost visible. We agreed the target and shipped streaming at 310 ms median first-audio latency without pretending the trade-off did not exist.",
        },
        {
            "competency": "Prioritisation",
            "question": "How do you decide what not to work on?",
            "star": {
                "situation": "The speech team had more model ideas than evaluation capacity.",
                "task": "I needed to protect the release path from low-value experiments.",
                "action": "I ranked work by expected user impact and required evidence, and made the CI gate the shared bar.",
                "result": "Low-value changes stopped consuming review time and releases became predictable.",
            },
            "answer": "I rank work by expected user impact and the evidence it needs, then use the release gate as the shared bar. At SautiFlow that meant low-value experiments stopped consuming review time. I would rather ship one measured improvement than five plausible ones nobody can compare.",
        },
        {
            "competency": "Conflict",
            "question": "Tell me about a disagreement over technical direction.",
            "star": {
                "situation": "A proposal favoured a larger model over fixing the evaluation data.",
                "task": "I had to argue for data quality without blocking the team.",
                "action": "I ran both approaches on a shared slice and showed the data fix moved WER more than the model change.",
                "result": "The team fixed the data first and kept the larger model for a later experiment.",
            },
            "answer": "A proposal favoured a larger model over fixing evaluation data. Instead of arguing in the abstract, I ran both on a shared slice. The data fix moved WER more than the model change, so we fixed the data first. The larger model stayed as a later experiment with a clear baseline.",
        },
        {
            "competency": "Learning",
            "question": "Tell me about learning a new area quickly.",
            "star": {
                "situation": "Vocalis needed provider-agnostic voice adapters and billing I had not built before.",
                "task": "I had to ship a working studio without locking the product to one provider.",
                "action": "I read the provider contracts, built one typed adapter seam, and tested settlement against simulated webhooks.",
                "result": "The studio shipped with Breeze and Fish Audio adapters behind one contract.",
            },
            "answer": "Vocalis needed provider-agnostic voice adapters and billing I had not built before. I read the provider contracts, built one typed adapter seam, and tested settlement against simulated webhooks. The studio shipped with two adapters behind one contract, which meant a provider change did not become a rewrite.",
        },
        {
            "competency": "Mentoring",
            "question": "How have you helped someone else grow?",
            "star": {
                "situation": "New engineers needed context on the audio pipeline and release process.",
                "task": "I wanted onboarding to depend less on me being in the room.",
                "action": "I wrote the pipeline and release documentation and paired on the first evaluation change.",
                "result": "New hires could run and explain the pipeline without waiting for a handover.",
            },
            "answer": "I wrote the pipeline and release documentation at SautiFlow and paired with new engineers on their first evaluation change. The goal was for onboarding not to depend on me being in the room. It worked because the docs described decisions and failure modes, not just commands.",
        },
        {
            "competency": "Pressure",
            "question": "Describe a time you had to deliver under a hard deadline.",
            "star": {
                "situation": "Streaming translation had a fixed demo date and a batch pipeline that was too slow.",
                "task": "I had to cut first-audio latency without claiming quality we had not measured.",
                "action": "I focused on chunking and KV caching, measured p50 and p95, and kept a fallback path.",
                "result": "The demo shipped at 310 ms median first-audio latency with a measured p95 of 780 ms.",
            },
            "answer": "Streaming translation had a fixed demo date and a batch pipeline that was too slow. I focused on chunking and KV caching, measured p50 and p95, and kept a fallback. We shipped at 310 ms median first-audio latency with a p95 of 780 ms, and the numbers were measured rather than estimated.",
        },
        {
            "competency": "Integrity",
            "question": "Tell me about a time you pushed back on a misleading metric.",
            "star": {
                "situation": "An aggregate WER looked good while one language had regressed.",
                "task": "I had to stop the release without hiding the overall result.",
                "action": "I added per-language slices to the report and showed the regression on the affected language.",
                "result": "The release was held and the model was fixed before it reached users.",
            },
            "answer": "An aggregate WER looked good while one language had regressed. I added per-language slices to the report and showed the regression rather than hiding behind the average. The release was held and fixed. A metric that hides the users who are failing is worse than no metric.",
        },
    ]
}
