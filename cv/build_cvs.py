"""Build one ATS-optimised CV per role from the facts published on the portfolio site.

Every metric below is lifted from index.html (work-experience and project sections)
or from the previous CV; no figures are invented. Run: python3 build_cvs.py
"""

import os
import subprocess

import docx_writer as d

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pdf')

NAME = 'LYLE OKOTH'
CONTACT_1 = 'Nairobi, Kenya  |  +254 797 668 066  |  lyleokoth.mlengineer@gmail.com'
CONTACT_2 = ('linkedin.com/in/lyle-okoth  |  github.com/lyle-mlengineer  |  '
             'lyle-mlengineer.github.io  |  medium.com/@lyle-okoth')

# Strict reverse-chronological order; variants only change bullet depth.
ORDER = ['researcher', 'product_dev', 'ml_engineer', 'data_engineer']

ROLES = {
    'researcher': {
        'title': 'Machine Learning Researcher',
        'org': 'SautiFlow Labs',
        'dates': '2026 - Present',
        'focus': 'Diffusion and flow-matching speech synthesis for languages with almost no public data.',
        'bullets': [
            'Trained a flow-matching TTS model covering **8 Kenyan languages** at **0.2s real-time factor** on a single '
            'consumer GPU, bringing multilingual synthesis inside interactive latency budgets.',
            'Cut **character error rate from 21% to 9%** on in-house Swahili and Sheng evaluation sets through fine-tuning, '
            'corpus curation and accent-aware text normalisation.',
            'Built a **120-hour** transcribed and force-aligned speech corpus from raw field recordings - the training base '
            'for the lab\'s synthesis and recognition models.',
            'Reduced **VRAM by 45%** with int8 quantization at a **0.4% accuracy cost**, cutting inference hardware per '
            'deployed voice.',
            'Published **4 models and 3 datasets on Hugging Face (12,000+ downloads)** with model cards, training recipes and '
            'reproducible evaluation baselines.',
            'Ran ablations tracked in Weights & Biases, reporting **WER / CER / MOS** per release so model choices hold up '
            'against a held-out test set.',
        ],
    },
    'product_dev': {
        'title': 'AI Product Developer',
        'org': 'Freelance',
        'dates': '2026 - Present',
        'focus': 'End-to-end ownership on a small number of products: research, flow design, model, launch, pricing, operation.',
        'bullets': [
            'Built **Voxa** alone from brief to live product: speech-skit generation, account system, **3 billing paths** and '
            'a studio interface for creators.',
            'Made infrastructure portable by design - storage swappable across local disk, **R2, S3 and Azure** with '
            '**no application code changes**.',
            'Modelled **Sheng and code-switched Kenyan dialogue** inside the product flow rather than bolting localisation on '
            'afterwards.',
            'Owned the full path: Figma flows, **FastAPI / PostgreSQL / Redis / Celery** backend, React interface and '
            'Playwright end-to-end tests.',
        ],
    },
    'ml_engineer': {
        'title': 'Machine Learning Engineer',
        'org': 'SautiFlow Labs',
        'dates': '2022 - 2026',
        'focus': 'Owned the path from checkpoint to service: pipelines, inference APIs, evaluation harnesses, cost control.',
        'bullets': [
            'Shipped the SemaScribe speaker-diarization pipeline, processing **50,000 hours of meeting audio at 12% '
            'diarization error rate**.',
            'Served speech inference on FastAPI + Celery + Redis at **8,000 requests/day at 180ms p95**, using ONNX Runtime, '
            'dynamic batching and GPU worker pools.',
            'Cut **training spend by 40%** with mixed precision and preemptible GPU capacity at **equal model quality**, '
            'verified on frozen evaluation sets.',
            'Automated ingestion of **200 hours of audio per week** with **98% label agreement across 3 reviewers** via ASR '
            'pre-labelling and reviewer rounds.',
            'Built a regression evaluation harness that caught **100% of quality drops before release across 6 shipped '
            'products**.',
            'Containerised deploys with Docker and GitHub Actions and tracked versions in MLflow for one-command rollback.',
        ],
    },
    'data_engineer': {
        'title': 'Software and Data Engineer',
        'org': 'SautiFlow Labs',
        'dates': '2022 - 2025',
        'focus': 'Two sides of one job: move data reliably, and ship a product people can actually use.',
        'bullets': [
            'Built SnapSavanna, a dataset and labeling platform hosting **18 African-language datasets and 40,000 labeled '
            'samples** with content-hash versioning.',
            'Designed domain-driven FastAPI services split into **5 bounded contexts** with ports and adapters at the edges, '
            'keeping model code out of the product path.',
            'Shipped SuraYa and EchoBuni with Google OAuth, **M-Pesa and card billing**, and swappable object storage across '
            '**R2, S3 and Azure**.',
            'Delivered server-sent events streaming for progressive audio generation with **first audio chunk under 400ms**.',
            'Built Airflow orchestration over Pandas, Parquet and DuckDB for ingestion, de-duplication and split generation.',
        ],
    },
}

PROJECTS = {
    'vocalis': ('Vocalis - Voice Design and Speech Studio',
                'Flow-matching TTS studio: brand voice design, cloning from short consented samples, 24/48 kHz masters, '
                'consent checks and audible watermarking, GPU inference queue with streamed output.',
                'PyTorch, torchaudio, VITS, Whisper, ONNX Runtime, FastAPI, Redis, Celery, React, Kubernetes'),
    'echoid': ('EchoiID - Speaker Diarization and ASR',
               'Who-spoke-when plus per-speaker transcription on stored files or live audio: voiceprint embeddings, clustering '
               'with overlap handling, word timestamps, SRT/VTT/JSON export.',
               'PyTorch, pyannote.audio, Whisper, FastAPI, WebSockets, Redis, Celery, PostgreSQL, Docker, AWS'),
    'labelset': ('LabelSet - Data and Labeling Platform',
                 'African-first corpora with ASR and detector pre-labelling, reviewer rounds, inter-annotator agreement, consent '
                 'records and COCO / LJSpeech / CVAT export layouts.',
                 'Python, FastAPI, PostgreSQL, DuckDB, Apache Airflow, MinIO, Label Studio, Whisper, YOLO, React'),
    'sautiflow': ('SautiFlow - AI Audio Skit Studio',
                  'Script to finished skit: prompt expansion into speaker-labelled scenes, multilingual TTS per character, '
                  'automatic timing, line-level re-takes, 15/30/60s export presets.',
                  'Python, FastAPI, PyTorch, VITS, Whisper, FFmpeg, Celery, Redis, PostgreSQL, Docker, AWS S3'),
    'plusone': ('PlusOne - AI Personal Photographer',
                'Event galleries from 4-6 selfies: per-person LoRA adapters, ControlNet composition, ArcFace identity gate, '
                'quality scoring and Real-ESRGAN print-resolution upscaling.',
                'PyTorch, Stable Diffusion, LoRA, ControlNet, ArcFace, Real-ESRGAN, FastAPI, Celery, Stripe'),
    'faceform': ('FaceForm - Synthetic Portrait Generator',
                 'Portrait diffusion checkpoint fine-tuned on a consented Kenyan face corpus, attribute adapters, seeded '
                 'variation, CodeFormer restoration, watermark and metadata tagging.',
                 'PyTorch, Stable Diffusion, LoRA, CodeFormer, ComfyUI, FastAPI, Next.js, PostgreSQL, AWS'),
}

EDUCATION = [
    ('BSc Computer Security and Forensics', 'Jaramogi Oginga Odinga University of Science and Technology (JOOUST)',
     '[20XX - 20XX]', 'ML, signal processing and security coursework; final-year project on audio watermarking for corpus provenance.'),
    ('Mechatronics Engineering', 'Jomo Kenyatta University of Agriculture and Technology (JKUAT)', '[20XX - 20XX]',
     'Fourier analysis, sampling theory, filter design and real-time embedded constraints - the grounding behind latency work.'),
]

EXTRAS = [
    '**Open ML releases:** 4 models and 3 datasets on Hugging Face, **12,000+ downloads**; model cards and training recipes per release.',
    '**Writing and tooling:** speech AI articles on Medium (@lyle-okoth); Python libraries for the YouTube and Google Drive APIs on PyPI.',
    '**Community:** OMDENA volunteer (2024); co-founder, SautiFlow Labs (2022).',
]

# ---------------------------------------------------------------- CV variants
VARIANTS = [
    {
        'slug': 'ML_Researcher',
        'headline': 'MACHINE LEARNING RESEARCHER - SPEECH SYNTHESIS AND AUDIO AI',
        'title': 'Machine Learning Researcher CV - Lyle Okoth',
        'keywords': ('speech synthesis, text-to-speech, flow matching, diffusion, ASR, diarization, LoRA, PEFT, quantization, '
                     'PyTorch, Hugging Face, Kenyan languages, WER, CER, MOS'),
        'summary': [
            'Machine Learning Researcher with **6+ years** building speech systems for Kenyan and other under-resourced languages, '
            'from raw field recordings to published models. Specialises in **diffusion and flow-matching TTS**, fine-tuned ASR and '
            'speaker diarization, plus the evaluation methodology that makes a result defensible.',
            'Trained a **0.2s RTF synthesizer covering 8 Kenyan languages** on one consumer GPU, cut Swahili/Sheng **CER from 21% to '
            '9%**, and released **4 models and 3 datasets with 12,000+ Hugging Face downloads**.',
        ],
        'skills': [
            ('Speech and audio', 'PyTorch, torchaudio, Hugging Face Transformers, Whisper, VITS, F5-TTS, pyannote.audio, librosa, '
                                 'soundfile, forced alignment, voice cloning'),
            ('Model training', 'Diffusion and flow-matching TTS, LoRA / PEFT, int8 quantization, DeepSpeed, Accelerate, Datasets, '
                               'CUDA, multi-GPU fine-tuning, preference tuning and guardrail pipelines'),
            ('Evaluation and research ops', 'WER / CER / MOS, DER, real-time factor, held-out test sets, ablation studies, '
                                            'Weights & Biases, MLflow, model cards, reproducible training recipes'),
            ('Speech data', 'Corpus building, consented field recording, noise and silence filtering, loudness normalisation, '
                            'Label Studio, reviewer agreement, FFmpeg, DuckDB, Parquet, Apache Airflow, S3'),
            ('Delivery', 'FastAPI, ONNX Runtime, Docker, GitHub Actions, AWS, Python, SQL, JavaScript'),
        ],
        'counts': {'researcher': 6, 'product_dev': 2, 'ml_engineer': 4, 'data_engineer': 2},
        'projects': ['vocalis', 'echoid'],
    },
    {
        'slug': 'ML_Engineer',
        'headline': 'MACHINE LEARNING ENGINEER - SPEECH AND AUDIO PRODUCTION',
        'title': 'Machine Learning Engineer CV - Lyle Okoth',
        'keywords': ('machine learning engineer, MLOps, LLMOps, model deployment, inference API, FastAPI, ONNX Runtime, quantization, '
                     'latency, cost optimisation, PyTorch, Hugging Face, evaluation harness, AWS, Docker, Kubernetes'),
        'summary': [
            'Machine Learning Engineer with **6+ years** taking speech models from checkpoint to production service: data pipelines, '
            'training, inference APIs, evaluation gates and cost control. End to end on Python, PyTorch and Hugging Face stacks served '
            'through FastAPI, Celery, Docker and AWS.',
            'Served **8,000 requests/day at 180ms p95**, ran **50,000 hours of audio** through a diarization pipeline at **12% DER**, '
            'cut **training spend by 40%**, and shipped a regression harness that caught **100% of quality drops before release '
            'across 6 products**.',
        ],
        'skills': [
            ('Deployment and MLOps', 'FastAPI, ONNX Runtime, TorchScript, WebSocket and SSE streaming, GPU batching, Docker, '
                                     'Kubernetes, GitHub Actions CI/CD, MLflow, Weights & Biases, rollback and drift monitoring'),
            ('Model training', 'PyTorch, Hugging Face Transformers, Whisper, VITS, LoRA / PEFT, quantization, distillation, mixed '
                               'precision, DeepSpeed, Accelerate, CUDA, preemptible GPU capacity'),
            ('Speech and audio', 'TTS, ASR, speech translation, speaker diarization, audio feature extraction, librosa, FFmpeg'),
            ('Evaluation', 'WER / CER / MOS / DER, latency and p95 budgets, regression harnesses, gold sets, A/B testing'),
            ('Data and infrastructure', 'Python, SQL, PostgreSQL, Redis, Celery, Apache Kafka, Apache Airflow, DuckDB, Parquet, '
                                        'Elasticsearch, S3, Cloudflare R2, Azure'),
        ],
        'counts': {'researcher': 4, 'product_dev': 2, 'ml_engineer': 6, 'data_engineer': 3},
        'projects': ['sautiflow', 'echoid'],
    },
    {
        'slug': 'Data_Engineer',
        'headline': 'DATA ENGINEER - ML DATA PLATFORMS AND SPEECH CORPORA',
        'title': 'Data Engineer CV - Lyle Okoth',
        'keywords': ('data engineer, data pipelines, ETL, ELT, Apache Airflow, data modeling, SQL, PostgreSQL, DuckDB, Parquet, S3, '
                     'data quality, annotation operations, dataset versioning, Python, FastAPI, Label Studio'),
        'summary': [
            'Data and Software Engineer with **6+ years** building the pipelines and platforms that make speech data trainable: '
            'ingestion, cleaning, ASR-assisted pre-labelling, reviewer workflows, versioned releases and the APIs that serve them.',
            'Automated ingestion of **200 hours of audio per week at 98% label agreement**, built a platform hosting **18 '
            'African-language datasets and 40,000 labeled samples**, and delivered a **120-hour** aligned training corpus.',
        ],
        'skills': [
            ('Pipelines and orchestration', 'Apache Airflow, Celery, Python ETL, batch and streaming jobs, retry-safe stages, '
                                            'incremental loads, de-duplication by content hash, dataset versioning'),
            ('Storage and data modeling', 'PostgreSQL, SQL data modeling, DuckDB, Parquet, Pandas, Polars, Elasticsearch, Redis, '
                                          'S3, Cloudflare R2, MinIO, Azure Blob'),
            ('Data quality and annotation ops', 'Label Studio, task schemas, reviewer rounds, inter-annotator agreement, gold sets, '
                                                'per-annotator accuracy, consent and licence records, dataset cards'),
            ('ML data preparation', 'FFmpeg, resampling, silence and noise filtering, loudness normalisation, forced alignment, '
                                    'diarization segmentation, train/val/test splits, COCO / LJSpeech / CVAT exports'),
            ('Platform engineering', 'FastAPI, domain-driven design, REST and SSE, Docker, GitHub Actions, AWS, Python, SQL, React'),
        ],
        'counts': {'researcher': 3, 'product_dev': 2, 'ml_engineer': 4, 'data_engineer': 5},
        'projects': ['labelset', 'echoid'],
    },
    {
        'slug': 'AI_Product_Engineer',
        'headline': 'AI PRODUCT ENGINEER - FULL-STACK BACKEND AND AI FEATURES',
        'title': 'AI Product Engineer CV - Lyle Okoth',
        'keywords': ('AI engineer, full stack engineer, backend engineer, FastAPI, React, PostgreSQL, Redis, Celery, payments, OAuth, '
                     'billing, LLM integration, speech API, Playwright, Figma, product shipping'),
        'summary': [
            'AI Product Engineer who ships speech and generative products end to end - research, model, backend, billing and interface - '
            'across **6 launched products** in **6+ years**. Built **Voxa** solo from brief to live service, including accounts, '
            '**3 billing paths** and a creator studio.',
            'Domain-driven **FastAPI** services with **5 bounded contexts**, Google OAuth, **M-Pesa, Stripe and card billing**, storage '
            'portable across **R2 / S3 / Azure**, and SSE streaming with **first audio chunk under 400ms**.',
        ],
        'skills': [
            ('Backend', 'Python, FastAPI, REST, SSE and WebSockets, Celery + Redis job queues, domain-driven design, ports and adapters, '
                        'PostgreSQL, retry-safe async pipelines'),
            ('Front-end and UX', 'JavaScript, React, Next.js, real-time streaming UIs, waveform and transcript views, Figma flows, '
                                 'onboarding design'),
            ('AI integration', 'Hugging Face Transformers, Whisper, VITS and flow-matching TTS, Stable Diffusion with LoRA, LLM prompt '
                               'pipelines, inference APIs, GPU worker queues'),
            ('Auth, billing and storage', 'Google OAuth, session handling, M-Pesa API, Stripe and card billing, Cloudflare R2, S3, '
                                          'Azure Blob behind one swappable interface'),
            ('Delivery and quality', 'Docker, GitHub Actions, AWS, Playwright E2E tests, logging and tracing, latency and cost tuning'),
        ],
        'counts': {'researcher': 2, 'product_dev': 4, 'ml_engineer': 3, 'data_engineer': 5},
        'projects': ['sautiflow', 'plusone', 'vocalis'],
    },
]


def bullet(text):
    return d.para('\u2022  ' + text, style='Bullet')


def build(v):
    p = [d.para(NAME, style='Name'),
         d.para(v['headline'], style='Headline'),
         d.para(CONTACT_1, style='Contact'),
         d.para(CONTACT_2, style='Contact')]

    p.append(d.para('Professional Summary', style='Section'))
    for s in v['summary']:
        p.append(d.para(s, style='Body'))

    p.append(d.para('Technical Skills', style='Section'))
    for label, items in v['skills']:
        p.append(bullet(f'**{label}:** {items}'))

    p.append(d.para('Work Experience', style='Section'))
    for key in ORDER:
        role = ROLES[key]
        p.append(d.tab_row(f"**{role['title']}**  |  {role['org']}", role['dates']))
        p.append(d.para(role['focus'], style='Sub'))
        for text in role['bullets'][:v['counts'][key]]:
            p.append(bullet(text))

    p.append(d.para('Selected Projects', style='Section'))
    for key in v['projects']:
        title, desc, tech = PROJECTS[key]
        p.append(d.para(f'**{title}**', style='Role', spacing='w:before="80" w:after="10"'))
        p.append(d.para(desc, style='Body', spacing='w:after="20"'))
        p.append(d.para(f'Tech: {tech}', style='Sub', spacing='w:after="40"'))

    p.append(d.para('Education', style='Section'))
    for degree, school, dates, note in EDUCATION:
        p.append(d.tab_row(f'**{degree}**  |  {school}', dates))
        p.append(d.para(note, style='Body', spacing='w:after="60"'))

    p.append(d.para('Open Source, Writing and Community', style='Section'))
    for text in EXTRAS:
        p.append(bullet(text))

    path = os.path.join(OUT, f"LYLE-OKOTH-CV-{v['slug']}.docx")
    d.write_docx(path, p, NAME.title(), v['title'], v['keywords'])
    return path


def main():
    paths = [build(v) for v in VARIANTS]
    subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', OUT, *paths],
                   check=True, capture_output=True)
    for path in paths:
        print(os.path.basename(path))


if __name__ == '__main__':
    main()
