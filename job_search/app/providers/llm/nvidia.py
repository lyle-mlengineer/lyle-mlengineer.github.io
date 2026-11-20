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

import logging
import random
import time
from typing import Any, Literal

import httpx

from ...config import DEFAULT_LLM_MODELS, NVIDIA_MODEL_FALLBACKS
from .base import ChatMessage, LLMProviderError, LLMResponse
from .openai_compat import OpenAICompatibleProvider

logger = logging.getLogger("skipper.llm")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

#: Defaults on NVIDIA NIM: Kimi writes, Nemotron Lightning drafts.
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
        model_fallbacks: tuple[str, ...] | list[str] | None = None,
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
        self.model_fallbacks = (
            tuple(model_fallbacks) if model_fallbacks is not None else NVIDIA_MODEL_FALLBACKS
        )
        self._retired_models: set[str] = set()

    # ------------------------------------------------------- retired models

    def _tier_for(self, model: str) -> str | None:
        for tier, value in self.models.items():
            if value == model:
                return tier
        return None

    def _substitute(self, model: str) -> str | None:
        """First usable id in the fallback chain that is not the retired one."""
        for candidate in self.model_fallbacks:
            if candidate != model and candidate not in self._retired_models:
                return candidate
        return None

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Literal["text", "json"] = "text",
        timeout_s: float | None = None,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """Retire a 404/410 model and retry on the next free endpoint.

        NVIDIA drops free models with a ``410 Gone`` body. That is not a
        transient failure and re-prompting cannot fix it, so the provider moves
        the tier onto the next model in ``model_fallbacks`` and remembers the
        swap for every later step in the run.
        """
        current = model or self.model_for("large")
        if current in self._retired_models:
            current = self._substitute(current) or current

        while True:
            try:
                return super().complete(
                    messages,
                    model=current,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout_s=timeout_s or self.timeout_s,
                    reasoning_effort=reasoning_effort,
                )
            except LLMProviderError as exc:
                if exc.status not in {404, 410}:
                    raise
                replacement = self._substitute(current)
                if replacement is None:
                    raise LLMProviderError(
                        f"{self.vendor} retired the model '{current}' and every configured "
                        "fallback model is unavailable. Update SKIPPER_NVIDIA_MODEL_LARGE/SMALL "
                        "or SKIPPER_NVIDIA_MODEL_FALLBACKS from build.nvidia.com/models.",
                        status=exc.status,
                        retryable=False,
                    ) from exc
                tier = self._tier_for(current)
                self._retired_models.add(current)
                if tier:
                    self.models[tier] = replacement
                logger.warning(
                    "%s retired model %s (%s); switched %s tier to %s",
                    self.vendor,
                    current,
                    exc.status,
                    tier or "requested",
                    replacement,
                )
                current = replacement

    def _reasoning_effort(self, requested: str | None, model: str) -> str | None:
        return normalize_effort(requested) or self.default_reasoning_effort

    def _relax(self, payload: dict[str, Any], body: str) -> dict[str, Any] | None:
        relaxed = dict(payload)
        changed = False
        lowered = body.lower()
        if "response_format" in relaxed and ("response_format" in lowered or "json" in lowered):
            relaxed.pop("response_format", None)
            changed = True
        # Nemotron's hosted shape uses chat_template_kwargs for thinking and may
        # reject reasoning_effort outright; drop it and let the model default.
        if "reasoning_effort" in relaxed and "reasoning" in lowered:
            relaxed.pop("reasoning_effort", None)
            changed = True
        return relaxed if changed else None
