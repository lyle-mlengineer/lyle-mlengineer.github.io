# Cover letter — Voxket.ai

**LYLE OKOTH**
Nairobi, Kenya · Remote (UTC+3) | +254 797 668 066 | lyleokoth.mlengineer@gmail.com
linkedin.com/in/lyle-okoth | github.com/lyle-mlengineer | lyle-mlengineer.github.io

17 November 2026

**Voxket.ai Hiring Team**
Remote

**Re: AI/ML Engineer — Speech & Audio**

Dear Voxket.ai Hiring Team,

I am applying for the AI/ML Engineer role at Voxket.ai. I build multilingual speech systems end to end, and the part of your description that stands out to me is that you are not integrating models — you are training, optimising and serving the intelligence behind real-time conversations. That is the work I have spent the last four years doing.

On model training, I cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 on 1,240 curated hours, comparing held-out and noisy field sets before promoting a run. I also built the evaluation harness — WER, CER, MOS and CI regression gates — that blocked nine model regressions from release in two quarters. On the synthesis side, I compressed a 1.6 GB TTS checkpoint to 480 MB with int8 quantisation and KV caching while raising capacity to 42 concurrent voices per GPU.

On inference and real-time serving, I shipped streaming speech-to-speech translation at 310 ms median first-audio latency (780 ms p95) across six language pairs on a single T4, down from a 1.4 s batch baseline. I work with ONNX Runtime, TensorRT, Triton and vLLM, and I tune batching, KV caching, FP16 and int8 paths against p50/p95 latency and cost, not benchmark averages. Deployment is Docker and Kubernetes on cloud GPUs, with the observability to catch drift and the guardrails to keep failures contained.

I have also shipped the products around those models: Vocalis for voice design and TTS, EchoID for speaker-aware transcription, and LabelSet for audio data at 11 speech task types. My code, models and project write-ups are at github.com/lyle-mlengineer; three speech datasets and two fine-tuned models are on Hugging Face. I am based in Nairobi (UTC+3) and available for remote work with overlap for your team.

I would welcome the chance to discuss how I can help Voxket.ai make multilingual, low-latency speech systems reliable at production scale.

Sincerely,

**Lyle Okoth**
AI/ML Engineer — Speech & Audio
