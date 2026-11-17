"""Build the Voxket.ai application package: tailored resume and cover letter.

Run from the repository root:
    /tmp/opencode/cv-venv/bin/python voxeet/build_application.py
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
base.LINKS = [link for link in base.LINKS if "medium.com" not in link[0]]

RESUME = {
    "file": str(ROOT / "LYLE-OKOTH-VOXKET-RESUME.docx"),
    "headline": "AI/ML ENGINEER | SPEECH & AUDIO — TRAINING, INFERENCE & REAL-TIME SERVING",
    "summary": (
        "Speech and audio AI engineer with four years of experience training, fine-tuning and serving multilingual "
        "speech models in production. Cut Swahili and Sheng ASR error rate from 23.4% to 11.8% with LoRA-tuned "
        "Whisper-large-v3, shipped streaming speech-to-speech translation at 310 ms median first-audio latency, and "
        "compressed a 1.6 GB TTS checkpoint to 480 MB while serving 42 concurrent voices per GPU. Works across the "
        "stack: PyTorch and Hugging Face training, ONNX Runtime / TensorRT / Triton / vLLM inference, int8 and FP16 "
        "optimisation, and Docker/Kubernetes deployment on cloud GPUs. Published 3 speech datasets and 2 fine-tuned "
        "models on Hugging Face."
    ),
    "competencies": [
        ("Speech & Audio Models", "ASR/STT (Whisper, wav2vec 2.0, NVIDIA NeMo), TTS (VITS, FastSpeech, XTTS-v2, "
                                   "Fish Audio, Breeze), speech translation (SeamlessM4T, NLLB-200), VAD, speaker "
                                   "diarisation and embeddings, speech enhancement, streaming audio"),
        ("Training & Fine-Tuning", "PyTorch, Hugging Face Transformers, PEFT / LoRA / QLoRA, distributed training "
                                    "(DDP / FSDP), mixed precision (FP16 / BF16), data curation and augmentation, "
                                    "WER / CER / MOS evaluation, Weights & Biases and MLflow"),
        ("Inference & Optimisation", "ONNX Runtime, TensorRT, Triton Inference Server, vLLM, TorchServe, int8 / FP16 "
                                      "/ NF4 quantisation, KV caching, continuous batching, CUDA-aware profiling, "
                                      "memory-efficient inference and p50/p95 latency tuning"),
        ("Real-Time & Infrastructure", "Streaming inference over WebSocket and WebRTC, FastAPI, Docker, Kubernetes, "
                                        "AWS and GCP GPU instances, GitHub Actions CI/CD, observability, throughput "
                                        "and cost optimisation"),
    ],
    "tech": [
        ("Languages", "Python, C++, SQL, JavaScript/TypeScript"),
        ("Speech & Audio", "PyTorch, Hugging Face Transformers, PEFT, Accelerate, ESPnet, NVIDIA NeMo, Coqui TTS, "
                            "pyannote.audio, torchaudio, librosa, FFmpeg"),
        ("Training", "DDP / FSDP, AMP (FP16 / BF16), LoRA / QLoRA, Optuna, Weights & Biases, MLflow"),
        ("Inference", "ONNX Runtime, TensorRT, Triton, vLLM, TorchServe, int8 / FP16 / NF4, KV caching, continuous "
                       "batching"),
        ("Platform", "FastAPI, WebSocket / WebRTC, Docker, Kubernetes, Redis, Celery, AWS, GCP, Render, GitHub Actions"),
    ],
    "jobs": [
        {
            "title": "Freelance AI Engineer",
            "company": "Independent, Remote",
            "dates": "2026 – Present",
            "bullets": [
                ("Built Vocalis, a voice-design and TTS studio: brief → design → audition → refine → synthesize, with "
                 "style, rate and volume controls, provider-agnostic Breeze and Fish Audio adapters, and a FastAPI + "
                 "Jinja2 monolith."),
                ("Built EchoID, a speaker-aware transcription studio: a pluggable ASR provider, speaker labels and "
                 "timestamps, reusable speaker profiles, search and filters, and JSON, TXT and PDF exports."),
                ("Built Suraya, an audit-driven latent-diffusion pipeline for Kenyan faces: an 889-image audit, face "
                 "detect and align, a compact 66M UNet on a frozen SD VAE, a VAE quality gate and KID-led evaluation."),
                ("Built LabelSet, an audio-first data platform: 11 speech task types, 16 kHz preprocessing, review and "
                 "JSONL export."),
            ],
        },
        {
            "title": "Machine Learning Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2024 – Present",
            "bullets": [
                ("Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 "
                 "on 1,240 curated hours, running distributed training and comparing held-out and noisy field sets "
                 "before promotion."),
                ("Shipped streaming speech-to-speech translation at 310 ms median / 780 ms p95 first-audio latency "
                 "across six language pairs on a single T4, down from a 1.4 s batch baseline."),
                ("Compressed a 1.6 GB TTS checkpoint to 480 MB with int8 quantisation and KV caching: 42 concurrent "
                 "voices per GPU, 3.1x throughput and 58% lower inference cost."),
                ("Built the evaluation harness — WER, CER, MOS and CI regression gates — which blocked 9 model "
                 "regressions from release in two quarters and standardised 60+ runs a month."),
            ],
        },
        {
            "title": "Data Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2023 – 2024",
            "bullets": [
                ("Designed batch and streaming pipelines (Airflow, Kafka, Spark) processing 6 TB / 38,000 hours of raw "
                 "audio a year into training-ready datasets for ASR, translation and TTS models."),
                ("Automated alignment and diarisation pre-labelling, cutting labelling from 11 to 3.5 minutes per audio "
                 "hour (68%); introduced DVC versioning and a dbt warehouse that cut compute spend 23%."),
            ],
        },
        {
            "title": "Software Engineer",
            "company": "SautiFlow Labs, Nairobi",
            "dates": "2022 – 2023",
            "bullets": [
                ("Built REST and WebSocket APIs in Django and Node.js handling 1.2M requests a day at p95 latency "
                 "under 140 ms, with PostgreSQL, Redis and Twilio integrations."),
                ("Introduced Docker deploys and GitHub Actions CI/CD — release cadence monthly to weekly — and took "
                 "front-end test coverage from 0 to 71%."),
            ],
        },
    ],
    "projects": [base.PROJECT_VOCALIS, base.PROJECT_ECHOID, base.PROJECT_LABELSET],
    "education": base.EDUCATION,
    "certs": base.CERTS,
    "extra": None,
    "references": False,
    "compact": True,
}


def build_cover_letter():
    doc = base.build_doc()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(base.NAME)
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = base.DARK

    contact = base.para(
        doc,
        f"{base.LOCATION}  |  {base.PHONE}  |  {base.EMAIL}",
        size=10,
        space_after=1,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    del contact

    links = doc.add_paragraph()
    links.alignment = WD_ALIGN_PARAGRAPH.CENTER
    links.paragraph_format.space_after = Pt(14)
    for i, (label, url) in enumerate(base.LINKS):
        if i:
            sep = links.add_run("  |  ")
            sep.font.size = Pt(9.5)
        base.add_hyperlink(links, url, label, size=9.5)

    base.para(doc, "17 November 2026", size=10.5, space_after=10)
    base.para(doc, "Voxket.ai Hiring Team", bold=True, size=10.5, space_after=2)
    base.para(doc, "Remote", size=10.5, space_after=10)
    base.para(doc, "Re: AI/ML Engineer — Speech & Audio", bold=True, size=10.5, space_after=10)

    base.para(doc, "Dear Voxket.ai Hiring Team,", size=10.5, space_after=8)

    paragraphs = [
        (
            "I am applying for the AI/ML Engineer role at Voxket.ai. I build multilingual speech systems end to end, "
            "and the part of your description that stands out to me is that you are not integrating models — you are "
            "training, optimising and serving the intelligence behind real-time conversations. That is the work I "
            "have spent the last four years doing."
        ),
        (
            "On model training, I cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning "
            "Whisper-large-v3 on 1,240 curated hours, comparing held-out and noisy field sets before promoting a run. "
            "I also built the evaluation harness — WER, CER, MOS and CI regression gates — that blocked nine model "
            "regressions from release in two quarters. On the synthesis side, I compressed a 1.6 GB TTS checkpoint to "
            "480 MB with int8 quantisation and KV caching while raising capacity to 42 concurrent voices per GPU."
        ),
        (
            "On inference and real-time serving, I shipped streaming speech-to-speech translation at 310 ms median "
            "first-audio latency (780 ms p95) across six language pairs on a single T4, down from a 1.4 s batch "
            "baseline. I work with ONNX Runtime, TensorRT, Triton and vLLM, and I tune batching, KV caching, FP16 and "
            "int8 paths against p50/p95 latency and cost, not benchmark averages. Deployment is Docker and Kubernetes "
            "on cloud GPUs, with the observability to catch drift and the guardrails to keep failures contained."
        ),
        (
            "I have also shipped the products around those models: Vocalis for voice design and TTS, EchoID for "
            "speaker-aware transcription, and LabelSet for audio data at 11 speech task types. My code, models and "
            "project write-ups are at github.com/lyle-mlengineer; three speech datasets and two fine-tuned models are "
            "on Hugging Face. I am based in Nairobi (UTC+3) and available for remote work with overlap for your team."
        ),
        (
            "I would welcome the chance to discuss how I can help Voxket.ai make multilingual, low-latency speech "
            "systems reliable at production scale."
        ),
    ]
    for text in paragraphs:
        base.para(doc, text, size=10.5, space_after=8)

    base.para(doc, "Sincerely,", size=10.5, space_after=18)
    base.para(doc, base.NAME, bold=True, size=10.5, space_after=2)
    base.para(doc, "AI/ML Engineer — Speech & Audio", size=10, space_after=0)

    path = ROOT / "LYLE-OKOTH-VOXKET-COVER-LETTER.docx"
    doc.save(str(path))
    print("saved", path)


if __name__ == "__main__":
    base.build(RESUME)
    build_cover_letter()
