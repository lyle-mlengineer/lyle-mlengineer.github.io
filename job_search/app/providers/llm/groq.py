"""Groq implementation of the LLM seam.

Groq speaks the OpenAI chat-completions wire format, so the only vendor-specific
details here are the base URL, the gpt-oss model names, and Groq's rate limits.
`openai/gpt-oss-*` are reasoning models; requests ask for low reasoning effort by
default and use `max_completion_tokens`, which is the field Groq documents.
"""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from .openai_compat import OpenAICompatibleProvider, TokenBucket, _retry_after_seconds

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

__all__ = [
    "GROQ_BASE_URL",
    "GroqProvider",
    "TokenBucket",
    "_retry_after_seconds",
]


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    vendor = "Groq"
    api_key_env = "SKIPPER_GROQ_API_KEY"
    max_tokens_field = "max_completion_tokens"

    def __init__(
        self,
        api_key: str,
        *,
        models: dict[str, str] | None = None,
        base_url: str = GROQ_BASE_URL,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        tpm: int = 30_000,
        client: httpx.Client | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        jitter=random.random,
    ) -> None:
        super().__init__(
            api_key,
            models=models
            or {"large": "openai/gpt-oss-120b", "small": "openai/gpt-oss-20b"},
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            tpm=tpm,
            client=client,
            sleep=sleep,
            clock=clock,
            jitter=jitter,
        )

    def _reasoning_effort(self, requested: str | None, model: str) -> str | None:
        # gpt-oss is a reasoning model: keep effort low unless the caller says otherwise.
        if requested:
            return requested
        return "low" if model.startswith("openai/gpt-oss") else None

    def _relax(self, payload: dict[str, Any], body: str) -> dict[str, Any] | None:
        # Groq has always accepted json_object; keep the wire format unchanged.
        return None
