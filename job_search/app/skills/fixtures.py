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
    "tech_groups": [
        {
            "name": "Languages",
            "items": ["Python", "C++", "JavaScript/TypeScript", "SQL"],
        },
        {
            "name": "Speech & ML",
            "items": ["PyTorch 2.x", "Hugging Face Transformers", "PEFT", "XTTS-v2", "pyannote.audio"],
        },
        {
            "name": "Serving & Infra",
            "items": ["FastAPI", "Triton Inference Server", "ONNX Runtime", "Docker", "Kubernetes"],
        },
        {
            "name": "Data & MLOps",
            "items": ["Apache Spark", "Airflow", "dbt", "DVC", "Weights & Biases"],
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
            "links": ["https://github.com/lyle-mlengineer/vocalis", "https://vocalis-rvcw.onrender.com"],
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
    "subject": "Six languages, one evaluation bar — Lyle Okoth",
    "body": "Hi Acme Speech team,\n\nYour posting talks about holding recognition quality across six languages, and that is the sentence that made me open the draft. At SautiFlow Labs the hardest problem was not adding another language; it was knowing whether the new one had made the others worse. I built the WER, CER and MOS harness that answered that question, then used it to take Swahili and Sheng word error rate from 23.4% to 11.8%.\n\nWhat I would want to work on with you is that same bar at a larger language set: evaluation that ships with the product, not after it. My CV and cover letter are attached. If that is useful, I would be glad to walk through the harness and where it broke.\n\nLyle",
    "attachment_names": ["CV", "Cover letter"],
}

FAKE_TELL = {
    "answer": "Most of my work starts with a microphone and a language that speech models treat as an afterthought. I came into machine learning through data engineering, so when I joined SautiFlow Labs I already knew how messy the audio pipeline was before a model ever saw it. That turned out to be the useful part. We had Swahili and Sheng recordings that nobody had measured properly, and I kept asking which errors actually reached a user.\n\nOne release made the answer obvious. The model sounded fine in a demo and failed on real callers, so I built the WER, CER and MOS harness and put it in CI. That harness took Swahili and Sheng word error rate from 23.4% to 11.8% and blocked nine regressions before they shipped. The same instinct carried into streaming: we got speech-to-speech translation to 310 ms median first-audio latency because we treated latency as a product constraint, not a benchmark.\n\nWhat I want next is a team where speech quality and serving economics are argued together. That is why this role stood out: the work is not just a better model, it is a better bar that the product can hold.",
    "delivery_notes": [
        "Start with the microphone line, then let the data-engineering detour explain how you work.",
        "Slow down on the evaluation story; it is the bridge to their quality bar.",
        "Land on the last sentence and stop. Do not add a list of skills.",
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
FAKE_SYSTEM_DESIGN = {
    "questions": [
        {
            "topic": "ASR serving",
            "difficulty": "core",
            "question": "Design a multilingual ASR service for six languages with per-tenant isolation.",
            "answer": (
                "I would start with the contract: upload or stream, language hint, partial transcripts, and a "
                "hard upload cap. The path is an API front door, a queue for long audio, and GPU workers with "
                "continuous batching. Each language has its own model entry in a registry, and a tenant maps "
                "to quotas, storage prefixes and a model version. I would stream partials over WebSocket and "
                "keep the batch path for files. At SautiFlow the streaming service ran at 310 ms median "
                "first-audio latency, so I know the front door and the model both count. The bottleneck is "
                "usually the queue when one language gets a burst, so isolation and autoscaling are explicit. "
                "I would log per-language WER on a sample, latency, and which model version answered."
            ),
            "trade_offs": [
                "Shared GPU pool is cheaper; per-language pools isolate noisy neighbours.",
                "Streaming gives faster feedback but makes partial accuracy harder to evaluate.",
                "A single model registry is simpler; regional deployments reduce data residency risk.",
            ],
            "requirements": {
                "functional": [
                    "Accept file uploads and live audio with a language hint.",
                    "Return partial transcripts for streams and a final transcript for files.",
                    "Keep tenants isolated by quota, storage prefix and model version.",
                ],
                "non_functional": [
                    "310 ms median first-audio latency, 780 ms p95.",
                    "A burst in one language must not starve the other five.",
                    "Per-language WER and model version are observable per request.",
                ],
            },
            "core_entities": [
                {
                    "name": "Tenant",
                    "fields": ["tenant_id", "quota_minutes", "storage_prefix", "model_version"],
                    "notes": "Owns isolation and billing.",
                },
                {"name": "TranscriptionJob", "fields": ["job_id", "tenant_id", "language", "status"]},
                {"name": "TranscriptSegment", "fields": ["job_id", "start_ms", "end_ms", "text", "confidence"]},
            ],
            "api_design": [
                {"method": "POST", "path": "/v1/transcriptions", "purpose": "Create a file or stream job."},
                {"method": "GET", "path": "/v1/transcriptions/{id}", "purpose": "Poll status and fetch the transcript."},
                {"method": "WS", "path": "/v1/stream", "purpose": "Send audio frames and receive partials."},
            ],
            "data_flow": [
                "The front door authenticates the tenant and writes the job row.",
                "Long audio goes to a queue; streams stay on a WebSocket session.",
                "A GPU worker pulls the job, batches by language and writes segments.",
                "The result store serves partials and the final transcript with the model version.",
            ],
            "high_level": [
                "API front door with auth, quotas and idempotency keys.",
                "Queue plus autoscaled GPU worker pool per language group.",
                "Model registry and object store for audio and transcripts.",
                "Metrics pipeline for latency, WER samples and per-tenant usage.",
            ],
            "deep_dives": [
                {
                    "title": "Burst isolation",
                    "detail": "Separate queues per language group and reserve a minimum worker count, so one tenant cannot consume the shared pool.",
                },
                {
                    "title": "Model rollout",
                    "detail": "Pin each job to a model version and shadow a candidate on sampled traffic before moving a tenant.",
                },
            ],
            "diagram": "client -> API front door -> queue -> GPU workers\n                          |                    |\n                          v                    v\n                     job store          model registry\n                          |\n                          v\n                    transcript store",
            "interviewer_questions": [
                "What happens when the queue backs up for one language?",
                "How do you roll back a model version for a single tenant?",
                "Where would you put a cache, and what would you key it on?",
            ],
            "questions_to_ask": [
                "How do you currently isolate a noisy tenant from the shared GPU pool?",
                "What is the release process for a new ASR model, and who signs off on a language-level regression?",
                "Which latency number does the team treat as the product SLO?",
            ],
            "follow_ups": [
                "How do you isolate a bad model version for one language?",
                "Where would you cache repeated uploads or transcripts?",
            ],
            "grounded_in": "Portfolio: SautiFlow multilingual ASR and streaming service",
        },
        {
            "topic": "Evaluation",
            "difficulty": "deep",
            "question": "Design the evaluation pipeline behind a speech model release gate.",
            "answer": (
                "The pipeline needs a locked, speaker-disjoint test set with a content hash, a runner that "
                "produces WER, CER and MOS, and a gate that compares a candidate with the current baseline. "
                "I would version the dataset and the metric code together, report every language and accent "
                "slice instead of one average, and fail the build when a slice regresses beyond its budget. "
                "At SautiFlow I built one harness across five ASR models and wired it into CI; in two quarters "
                "it blocked nine regressions from release. The key design choice is that the gate returns a "
                "release decision, not a dashboard. A human reviews only the slices that moved."
            ),
            "trade_offs": [
                "A locked test set prevents leakage but needs a separate refresh process.",
                "More slices catch real regressions but increase runtime and review noise.",
                "Human MOS is trustworthy but slow; automated proxies are cheap but can drift.",
            ],
            "follow_ups": [
                "How do you detect that the test set has aged?",
                "What would you do when only one low-resource language regresses?",
            ],
            "grounded_in": "Portfolio: SautiFlow evaluation harness and CI gate",
        },
        {
            "topic": "Streaming",
            "difficulty": "core",
            "question": "Design a speech-to-speech translation path with sub-second first audio.",
            "answer": (
                "I would split the path into streaming ASR, translation and streaming TTS, with small chunks "
                "and a shared session id. The ASR worker keeps the encoder warm, the translator consumes "
                "partials with a short lookahead, and TTS starts on the first stable phrase rather than the "
                "whole sentence. KV caching and avoiding a synchronous hop between services matter more than "
                "a bigger model. At SautiFlow this approach shipped at 310 ms median first-audio latency and "
                "780 ms p95, down from a 1.4 second batch baseline. I would measure p50 and p95 per hop and "
                "keep a batch fallback for long recordings."
            ),
            "trade_offs": [
                "Shorter chunks lower latency but can reduce translation quality.",
                "Keeping sessions warm costs GPU memory; cold starts hurt p95.",
                "A batch fallback protects quality but needs a separate code path.",
            ],
            "follow_ups": [
                "Where does p95 usually blow up in this design?",
                "How would you handle code-switching mid-sentence?",
            ],
            "grounded_in": "Portfolio: SautiFlow streaming translation",
        },
        {
            "topic": "TTS platform",
            "difficulty": "core",
            "question": "Design a TTS studio that can switch providers without a rewrite.",
            "answer": (
                "The studio should depend on one typed provider contract: list voices, synthesise, clone, and "
                "report cost. Each provider adapter translates its own errors and returns the same audio "
                "format, so the queue and player never learn provider-specific details. A registry chooses "
                "the provider from configuration, and a fallback policy handles an outage. At Vocalis I built "
                "Breeze and Fish Audio adapters behind one contract, which meant a provider change did not "
                "become a product rewrite. I would add per-tenant quotas, idempotent take ids, and store the "
                "provider and voice on every generated take for reproducibility."
            ),
            "trade_offs": [
                "Normalising audio server-side costs CPU but removes player differences.",
                "A fallback provider improves uptime but voices will not match exactly.",
                "Cloning gives a personal voice but raises consent and deletion requirements.",
            ],
            "follow_ups": [
                "How do you test a provider adapter without calling the vendor?",
                "What happens to an in-flight take when a provider fails?",
            ],
            "grounded_in": "Portfolio: Vocalis provider adapters",
        },
    ]
}

FAKE_LOW_LEVEL_DESIGN = {
    "questions": [
        {
            "topic": "Provider seam",
            "difficulty": "core",
            "question": (
                "Design the low-level interface for a speech provider registry that can swap ASR, TTS and "
                "translation vendors without callers changing."
            ),
            "answer": (
                "Start with the smallest contract the callers actually need: an id, a capability list, and "
                "one method per capability that takes a typed request and returns a typed result. Keep vendor "
                "errors out of the contract by translating them into a small error hierarchy at the adapter "
                "boundary. The registry owns construction and configuration, caches one adapter per name, "
                "and exposes a health check so the UI can disable a tab instead of failing at call time. "
                "Every result should carry the provider and model that produced it. In my portfolio the "
                "same shape let Breeze and Fish Audio sit behind one TTS adapter without touching the audio "
                "pipeline."
            ),
            "components": [
                "Provider protocol with typed request and result objects",
                "Adapter per vendor that translates errors and payloads",
                "Registry built from settings plus a health check",
            ],
            "requirements": {
                "functional": [
                    "Callers ask for a capability, not a vendor.",
                    "Adapters can be swapped from configuration at start-up.",
                ],
                "non_functional": [
                    "A vendor failure must not leak vendor-specific exceptions.",
                    "Health checks must not block the audio request path.",
                ],
            },
            "core_entities": [
                {"name": "SpeechRequest", "fields": ["text", "voice", "format", "timeout_s"], "notes": "Immutable."},
                {"name": "SpeechResult", "fields": ["audio", "mime_type", "provider", "model", "cost_usd"]},
                {"name": "Provider", "fields": ["name", "capabilities", "synthesise()", "health()"]},
            ],
            "class_design": [
                {
                    "name": "Provider",
                    "responsibility": "Protocol every vendor adapter implements; the only type callers depend on.",
                    "interfaces": ["synthesise(request) -> SpeechResult", "health() -> bool"],
                    "collaborators": ["SpeechRequest", "SpeechResult"],
                },
                {
                    "name": "Registry",
                    "responsibility": "Constructs adapters from settings and returns a cached instance by name.",
                    "interfaces": ["get(name) -> Provider", "available() -> list[str]"],
                    "collaborators": ["Provider", "Settings"],
                },
                {
                    "name": "ProviderError",
                    "responsibility": "One error hierarchy with a retryable flag; vendor payloads stay inside adapters.",
                    "interfaces": ["retryable: bool", "provider: str"],
                    "collaborators": [],
                },
            ],
            "implementation": [
                {
                    "title": "Request boundary",
                    "detail": "The caller builds an immutable SpeechRequest. The adapter validates fields and translates to the vendor payload; callers never see vendor JSON.",
                },
                {
                    "title": "Error translation",
                    "detail": "Each adapter catches vendor exceptions and raises ProviderError with retryable set. Retry and fallback policy lives above the registry, not inside every adapter.",
                },
                {
                    "title": "Caching",
                    "detail": "The registry builds each adapter once and caches it by name. Health checks are cheap and non-blocking so the UI can disable a provider without a request timeout.",
                },
                {
                    "title": "Tests",
                    "detail": "A shared contract test runs every adapter against the same request/result fixtures, plus one test per vendor error mapping.",
                },
            ],
            "extensibility": [
                "Add a new capability as a separate protocol so existing adapters and callers do not change.",
                "Add a vendor by implementing Provider and registering a factory; no pipeline edits.",
                "A streaming variant can return an iterator through a StreamingProvider protocol rather than widening Provider.",
            ],
            "api_design": [
                {"path": "Provider.synthesise(request) -> SpeechResult", "purpose": "One typed call per capability."},
                {"path": "Registry.get(name) -> Provider", "purpose": "Return a cached adapter or raise Unavailable."},
                {"path": "Provider.health() -> bool", "purpose": "Cheap check used by the UI and routing."},
            ],
            "data_flow": [
                "The caller builds an immutable request and asks the registry for a provider.",
                "The adapter validates fields and translates the request to the vendor payload.",
                "Vendor errors become ProviderError with retryable set at the boundary.",
                "The adapter returns a result carrying the provider and model that answered.",
            ],
            "high_level": [
                "A protocol at the seam and one adapter class per vendor.",
                "A registry that constructs adapters from settings and caches them.",
                "A small error hierarchy so retries and fallbacks live above the adapters.",
            ],
            "deep_dives": [
                {
                    "title": "Protocol evolution",
                    "detail": "Add a new optional capability as a separate protocol so existing adapters keep compiling and no caller checks feature flags.",
                },
                {
                    "title": "Retry ownership",
                    "detail": "Classify errors in the adapter and retry in one caller-level policy, so every vendor gets the same backoff and budget.",
                },
            ],
            "diagram": "Caller -> Registry.get() -> Provider protocol\n                                  |\n                     +------------+------------+\n                     v            v            v\n                  Breeze      Fish Audio   Fake",
            "interviewer_questions": [
                "How do you add a vendor with streaming without changing existing callers?",
                "Where should timeouts be enforced, in the adapter or the registry?",
                "How would you test the contract across every adapter?",
            ],
            "questions_to_ask": [
                "How many speech providers does the team support today, and what breaks when one changes its API?",
                "Who owns the retry budget when a vendor is slow but not failing?",
                "How does the team test a provider contract without calling the live vendor in CI?",
            ],
            "data_structures": [
                "Immutable request dataclass (text, voice, format, timeout)",
                "Result dataclass carrying bytes, mime type, provider, model and cost",
            ],
            "trade_offs": [
                "A narrow contract is easy to implement but may hide vendor-specific controls.",
                "A capability list avoids runtime surprises but needs a default when a provider lacks one.",
            ],
            "follow_ups": [
                "How would you evolve the protocol without breaking existing adapters?",
                "Where would you put retries so every adapter gets the same policy?",
            ],
            "grounded_in": "Portfolio: Vocalis provider adapters",
        },
        {
            "topic": "Evaluation harness",
            "difficulty": "deep",
            "question": (
                "Design the classes and data flow for an evaluation harness that can compare five ASR "
                "models on the same locked test set and return a release decision."
            ),
            "answer": (
                "Model the test set as an immutable manifest: audio ids, references, language and accent "
                "slices, and a content hash. A loader validates the hash and returns typed samples, so a "
                "silent dataset edit fails before any GPU time is spent. Each model adapter exposes "
                "transcribe(sample) and returns a hypothesis with the model version. A metric object owns "
                "normalisation and scoring per slice; the runner only orchestrates. The gate compares the "
                "candidate with a stored baseline and returns a decision plus the slices that regressed. "
                "Results are append-only rows keyed by run id, model version and dataset hash, which makes "
                "a release reproducible."
            ),
            "components": [
                "Dataset manifest and loader with hash validation",
                "Model adapters implementing transcribe(sample)",
                "Metric objects for WER, CER and per-slice aggregation",
                "Gate that compares a candidate with a baseline",
            ],
            "data_structures": [
                "Manifest records keyed by audio id with slice metadata",
                "Hypothesis record: audio id, text, model version, latency",
                "Score table keyed by (run, model, slice) for cheap comparison",
            ],
            "trade_offs": [
                "Scoring every slice is slower but stops an average from hiding a regression.",
                "An immutable manifest costs storage but makes a release decision defensible.",
                "Running models in parallel shortens the loop but complicates GPU scheduling.",
            ],
            "follow_ups": [
                "How would you make the gate deterministic when decoding is stochastic?",
                "What would you cache between runs, and how would you invalidate it?",
            ],
            "grounded_in": "Portfolio: SautiFlow evaluation harness and release gate",
        },
        {
            "topic": "Streaming session",
            "difficulty": "core",
            "question": (
                "Design the low-level state machine for one streaming ASR WebSocket session, including "
                "backpressure and cancellation."
            ),
            "answer": (
                "Use an explicit state enum: connecting, authenticating, streaming, draining, closed, failed. "
                "Each state accepts only a small set of events and rejects the rest with a typed error. "
                "Audio frames enter a bounded queue; when it is full the session applies backpressure instead "
                "of growing memory. A writer task owns the model call and emits partial transcripts with a "
                "monotonic sequence number, so the client can drop stale partials. Cancellation closes the "
                "queue, waits for the writer to acknowledge, and records why the session ended. Timeouts live "
                "in one place, not in each handler."
            ),
            "components": [
                "Session object holding state, queue and sequence counter",
                "Reader task for frames and writer task for partial transcripts",
                "Bounded queue with an explicit overflow policy",
            ],
            "data_structures": [
                "Enum for session state and a small event union",
                "Bounded FIFO of audio frames",
                "Sequence-numbered partial transcript record",
            ],
            "trade_offs": [
                "Dropping frames keeps latency bounded but loses audio; blocking preserves accuracy.",
                "One writer task serialises model calls but can become the bottleneck per session.",
            ],
            "follow_ups": [
                "How would you recover a session after a transient model failure?",
                "Where would you measure first-audio latency?",
            ],
            "grounded_in": "Portfolio: SautiFlow streaming ASR",
        },
    ]
}

FAKE_CODING = {
    "problems": [
        {
            "topic": "Intervals",
            "difficulty": "warm-up",
            "question": "Merge overlapping audio segments so a batch job never transcribes the same audio twice.",
            "answer": (
                "Sort by start time, then walk the list once. If the next segment starts before the current "
                "end, extend the end; otherwise close the current segment and start a new one. Sorting "
                "dominates at O(n log n), and the merge pass is O(n) space for the output."
            ),
            "approach": "Sort by start, merge in one pass, and keep half-open intervals so touching segments do not overlap.",
            "slow_approach": "Merge every pair by rescanning the output list for an overlap, then restart. It is the obvious first pass and is quadratic in the number of segments.",
            "slow_code": (
                "def merge_segments(segments):\n"
                "    merged = []\n"
                "    for start, end in segments:\n"
                "        for current in merged:\n"
                "            if start <= current[1] and end >= current[0]:\n"
                "                current[0] = min(current[0], start)\n"
                "                current[1] = max(current[1], end)\n"
                "                break\n"
                "        else:\n"
                "            merged.append([start, end])\n"
                "    return merged\n"
            ),
            "slow_time_complexity": "O(n²)",
            "slow_space_complexity": "O(n)",
            "requirements": {
                "functional": [
                    "Merge overlapping half-open intervals.",
                    "Keep touching intervals separate.",
                ],
                "non_functional": [
                    "O(n log n) time and O(n) output space.",
                    "One pass after sorting, with no mutation of the input.",
                ],
            },
            "core_entities": [
                {"name": "Interval", "fields": ["start_ms", "end_ms"], "notes": "Half-open: start <= t < end."},
            ],
            "api_design": [
                {"path": "merge_segments(segments: list[tuple[int, int]]) -> list[list[int]]", "purpose": "Merge and return new intervals."},
            ],
            "data_flow": [
                "Sort intervals by start time.",
                "Walk once, extending the last merged interval when it overlaps.",
                "Otherwise append the interval and continue.",
            ],
            "high_level": [
                "Sorting makes overlap a local decision between the current interval and the last output.",
                "The output list is the only state, so the algorithm is easy to test.",
            ],
            "deep_dives": [
                {
                    "title": "Half-open intervals",
                    "detail": "Treating end as exclusive means [0, 10) and [10, 20) stay separate, which matches audio segment boundaries.",
                },
                {
                    "title": "Streaming variant",
                    "detail": "Keep only the last open interval and emit it once a later start passes its end; memory becomes O(1).",
                },
            ],
            "diagram": "[(0,10), (5,12), (20,30)]\n        |\n        v\n sort -> [(0,10), (5,12), (20,30)]\n        |\n        v\n merge -> [[0,12], [20,30]]",
            "interviewer_questions": [
                "What changes if intervals are closed?",
                "How would you merge a stream that does not fit in memory?",
                "How would you prove the output is minimal?",
            ],
            "questions_to_ask": [
                "How do you detect overlapping audio segments before they reach the transcription queue?",
                "When a batch window is full, does the scheduler reject work or spill to a second GPU?",
                "How do you test this merge against real production segment patterns?",
            ],
            "code": (
                "def merge_segments(segments):\n"
                "    ordered = sorted(segments, key=lambda item: item[0])\n"
                "    merged = []\n"
                "    for start, end in ordered:\n"
                "        if start >= end:\n"
                "            continue\n"
                "        if merged and start < merged[-1][1]:\n"
                "            merged[-1][1] = max(merged[-1][1], end)\n"
                "        else:\n"
                "            merged.append([start, end])\n"
                "    return merged\n"
            ),
            "language": "Python",
            "complexity": "O(n log n) time · O(n) space",
            "time_complexity": "O(n log n)",
            "space_complexity": "O(n)",
            "edge_cases": ["Empty input", "Zero-length segment", "Segments already sorted", "One segment contains another"],
            "follow_ups": ["How would you stream this without storing every segment?", "What changes for closed intervals?"],
        },
        {
            "topic": "Evaluation",
            "difficulty": "core",
            "question": "Compute word error rate for a reference and hypothesis transcript.",
            "answer": (
                "WER is the edit distance over words divided by the reference length. Build a DP table where "
                "each cell is the cheapest substitution, insertion or deletion, then backtrack or keep the "
                "final cell. The table is O(mn) time and O(mn) space, or O(n) space if only the score is "
                "needed. Empty references and normalisation need an explicit policy."
            ),
            "approach": "Tokenise and normalise both strings, run Levenshtein over tokens, divide by the reference length.",
            "code": (
                "def word_error_rate(reference, hypothesis):\n"
                "    ref = reference.lower().split()\n"
                "    hyp = hypothesis.lower().split()\n"
                "    if not ref:\n"
                "        return 0.0 if not hyp else 1.0\n"
                "    previous = list(range(len(hyp) + 1))\n"
                "    for i, ref_word in enumerate(ref, start=1):\n"
                "        current = [i]\n"
                "        for j, hyp_word in enumerate(hyp, start=1):\n"
                "            cost = 0 if ref_word == hyp_word else 1\n"
                "            current.append(min(\n"
                "                previous[j] + 1,\n"
                "                current[j - 1] + 1,\n"
                "                previous[j - 1] + cost,\n"
                "            ))\n"
                "        previous = current\n"
                "    return previous[-1] / len(ref)\n"
            ),
            "language": "Python",
            "complexity": "O(mn) time · O(n) space",
            "edge_cases": ["Empty reference", "Empty hypothesis", "Punctuation differences", "Repeated words"],
            "follow_ups": ["How would you report per-language WER?", "When would you use CER instead?"],
        },
        {
            "topic": "Scheduling",
            "difficulty": "core",
            "question": "Batch audio jobs into fixed-size GPU windows while minimising the number of windows.",
            "answer": (
                "This is bin packing: sort durations descending, then place each job in the first window with "
                "enough room, opening a new one only when none fits. First-fit decreasing is not optimal but "
                "is fast and predictable. For exact minimum windows, use backtracking or an integer solver, "
                "which is rarely worth it for a queue."
            ),
            "approach": "First-fit decreasing keeps the common case fast; track remaining capacity per window.",
            "code": (
                "def pack_batches(durations, window):\n"
                "    if window <= 0:\n"
                "        raise ValueError('window must be positive')\n"
                "    batches = []\n"
                "    for duration in sorted(durations, reverse=True):\n"
                "        if duration > window:\n"
                "            raise ValueError('job exceeds window')\n"
                "        for batch in batches:\n"
                "            if batch['used'] + duration <= window:\n"
                "                batch['jobs'].append(duration)\n"
                "                batch['used'] += duration\n"
                "                break\n"
                "        else:\n"
                "            batches.append({'jobs': [duration], 'used': duration})\n"
                "    return batches\n"
            ),
            "language": "Python",
            "complexity": "O(n²) worst case · O(n) space",
            "edge_cases": ["Job longer than the window", "Zero-length jobs", "All jobs identical", "Empty queue"],
            "follow_ups": ["How would you preserve tenant fairness?", "What if jobs can be split?"],
        },
        {
            "topic": "Rate limiting",
            "difficulty": "core",
            "question": "Implement a per-tenant sliding-window rate limiter for a TTS API.",
            "answer": (
                "Keep a deque of timestamps per tenant. On each request, drop timestamps older than the "
                "window, reject if the deque is full, otherwise append now. Each decision is amortised O(1) "
                "and memory is bounded by the limit per tenant. A monotonic clock avoids wall-clock jumps, "
                "and shared storage is needed once there is more than one API instance."
            ),
            "approach": "One deque per tenant, prune expired entries before checking the limit.",
            "code": (
                "from collections import defaultdict, deque\n"
                "import time\n"
                "\n"
                "class SlidingWindowLimiter:\n"
                "    def __init__(self, limit, window_seconds, clock=time.monotonic):\n"
                "        self.limit = limit\n"
                "        self.window = window_seconds\n"
                "        self.clock = clock\n"
                "        self.hits = defaultdict(deque)\n"
                "\n"
                "    def allow(self, tenant):\n"
                "        now = self.clock()\n"
                "        hits = self.hits[tenant]\n"
                "        while hits and hits[0] <= now - self.window:\n"
                "            hits.popleft()\n"
                "        if len(hits) >= self.limit:\n"
                "            return False\n"
                "        hits.append(now)\n"
                "        return True\n"
            ),
            "language": "Python",
            "complexity": "O(1) amortised per request · O(limit) space per tenant",
            "edge_cases": ["Limit of zero", "Burst exactly at the boundary", "Many idle tenants", "Multiple API instances"],
            "follow_ups": ["How would you make this distributed?", "What would you return to a throttled client?"],
        },
    ]
}


# Practice questions are not tied to a pack artifact: they are short drills
# generated from uploaded sources, the posting and the portfolio.
FAKE_PRACTICE = {
    "questions": [
        {
            "topic": "Low-level design",
            "difficulty": "core",
            "question": "Why would you put a bounded queue between an audio reader and a model writer?",
            "answer": (
                "A bounded queue turns an unbounded memory risk into an explicit policy. The reader can slow "
                "down, drop frames or close the session, and the writer owns the expensive model call without "
                "the reader blocking on it. The bound is also a latency budget: if the queue is full, the "
                "system is already too far behind to answer in real time. I would expose the depth and the "
                "overflow count as metrics, and choose drop-oldest for streaming and block for batch."
            ),
            "follow_ups": [
                "What would you alert on?",
                "How does the policy change for batch transcription?",
            ],
            "source": "Interview sources",
        },
        {
            "topic": "Evaluation",
            "difficulty": "deep",
            "question": "How do you stop a locked evaluation set from leaking into training?",
            "answer": (
                "Treat the manifest as the source of truth: store a content hash, keep the test audio outside "
                "the training bucket, and make the training loader reject any id that appears in the test "
                "manifest. The gate should record the dataset hash with every result so a score can be tied "
                "to exactly one dataset. I would also rotate a small, never-published audit slice to catch "
                "overfitting that a fixed set cannot show."
            ),
            "follow_ups": [
                "Where would the check live so every training job runs it?",
                "How would you handle near-duplicate recordings?",
            ],
            "source": "Interview sources",
        },
        {
            "topic": "Python",
            "difficulty": "warm-up",
            "question": "When is a dataclass the wrong choice for a request object?",
            "answer": (
                "A dataclass is a poor fit when the object must be cheap to create in a very hot loop, when "
                "mutation is part of the contract, or when the object needs behaviour that belongs to a "
                "service. It is also wrong if the fields are not known until runtime. For a request crossing "
                "a process boundary I would rather use a validated model with an explicit schema."
            ),
            "follow_ups": [
                "How would you validate a dataclass at the boundary?",
                "When would you choose a NamedTuple instead?",
            ],
            "source": "Interview sources",
        },
    ]
}

FAKE_ANSWER = {
    "answer": (
        "A provider seam should expose the smallest contract the callers need, translate vendor errors at "
        "the adapter boundary, and carry the provider and model on every result. The registry builds the "
        "adapter from configuration and exposes a health check, so a missing key disables the tab instead "
        "of failing mid-request. I would keep retries in one shared wrapper and make each adapter's "
        "capabilities explicit rather than guessing from the provider name."
    ),
    "follow_ups": [
        "How would you add a provider without changing the callers?",
        "Where would you put the cost calculation?",
    ],
    "confidence": "high",
}
