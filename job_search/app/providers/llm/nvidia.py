"""NVIDIA NIM provider, wired for the hosted DeepSeek models.

NVIDIA's ``integrate.api.nvidia.com`` endpoint is OpenAI-compatible, so this
module only names the base URL, the DeepSeek model ids and the DeepSeek reasoning
vocabulary. Two details are worth knowing:

* DeepSeek V4 models accept ``reasoning_effort`` of ``none``, ``high`` or ``max``
  (NVIDIA maps it onto the model's thinking mode). Thinking is off by default
  here: the pipeline makes eleven short calls per job and paying for maximum
  reasoning on each one is the difference between cents and dollars.
* ``max_tokens`` is the documented field, not Groq's ``max_completion_tokens``.

Structured output is supported, but a trial key can still reject
``response_format``; when that happens the request is retried once without it and
the JSON instruction already in the prompt carries the payload.
"""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from ...config import DEFAULT_LLM_MODELS
from .openai_compat import OpenAICompatibleProvider

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

#: DeepSeek defaults on NVIDIA NIM: the pro model writes, flash drafts.
NVIDIA_MODELS: dict[str, str] = dict(DEFAULT_LLM_MODELS["nvidia"])

#: DeepSeek V4 exposes three thinking modes; older effort words collapse onto them.
REASONING_EFFORTS: dict[str, str] = {
    "none": "none",
    "off": "none",
    "low": "none",
    "medium": "high",
    "high": "high",
    "max": "max",
}

ALLOWED_EFFORTS: tuple[str, ...] = ("none", "high", "max")


def normalize_effort(value: str | None) -> str | None:
    if not value:
        return None
    return REASONING_EFFORTS.get(value.strip().lower())


class NvidiaProvider(OpenAICompatibleProvider):
    name = "nvidia"
    vendor = "NVIDIA"
    api_key_env = "SKIPPER_NVIDIA_API_KEY"
    max_tokens_field = "max_tokens"
    default_reasoning_effort = "none"
    empty_completion_hint = (
        "DeepSeek may have spent the whole budget on reasoning; "
        "lower reasoning effort or raise max_tokens"
    )

    def __init__(
        self,
        api_key: str,
        *,
        models: dict[str, str] | None = None,
        base_url: str = NVIDIA_BASE_URL,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        tpm: int = 40_000,
        reasoning_effort: str | None = "none",
        client: httpx.Client | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        jitter=random.random,
    ) -> None:
        super().__init__(
            api_key,
            models=models or dict(NVIDIA_MODELS),
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            tpm=tpm,
            client=client,
            sleep=sleep,
            clock=clock,
            jitter=jitter,
        )
        self.default_reasoning_effort = normalize_effort(reasoning_effort) or "none"

    def _reasoning_effort(self, requested: str | None, model: str) -> str | None:
        return normalize_effort(requested) or self.default_reasoning_effort

    def _relax(self, payload: dict[str, Any], body: str) -> dict[str, Any] | None:
        if "response_format" not in payload:
            return None
        lowered = body.lower()
        if "response_format" not in lowered and "json" not in lowered:
            return None
        relaxed = dict(payload)
        relaxed.pop("response_format", None)
        return relaxed
