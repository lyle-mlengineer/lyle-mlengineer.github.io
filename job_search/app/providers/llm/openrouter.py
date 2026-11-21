"""OpenRouter provider.

OpenRouter is an OpenAI-compatible gateway in front of many vendors. The
``openrouter/free`` router picks any model whose prompt and completion prices are
zero and that supports the features in the request (here: JSON output), so the
default tiers stay free even as the free-model catalogue rotates. Pin a concrete
``:free`` id with ``SKIPPER_OPENROUTER_MODEL_LARGE/SMALL`` when reproducibility
matters; free ids are listed in ``.env.example``.

The endpoint uses ``max_tokens`` and accepts ``response_format`` on most models.
If an individual free model rejects JSON mode, the provider retries once without
it and the JSON instruction already in the prompt carries the answer.
"""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from ...config import DEFAULT_LLM_MODELS
from .openai_compat import OpenAICompatibleProvider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

__all__ = ["OPENROUTER_BASE_URL", "OpenRouterProvider"]


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    vendor = "OpenRouter"
    api_key_env = "SKIPPER_OPENROUTER_API_KEY"
    max_tokens_field = "max_tokens"
    empty_completion_hint = "the free model may have refused JSON output; retry or pin another free id"

    def __init__(
        self,
        api_key: str,
        *,
        models: dict[str, str] | None = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        tpm: int = 20_000,
        referer: str = "",
        title: str = "Skipper",
        client: httpx.Client | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        jitter=random.random,
    ) -> None:
        self.referer = referer.strip()
        self.title = title.strip()
        super().__init__(
            api_key,
            models=models or dict(DEFAULT_LLM_MODELS["openrouter"]),
            base_url=base_url,
            timeout_s=timeout_s,
            max_retries=max_retries,
            tpm=tpm,
            client=client,
            sleep=sleep,
            clock=clock,
            jitter=jitter,
        )

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        # Optional attribution headers recommended by OpenRouter.
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.title:
            headers["X-Title"] = self.title
        return headers

    def _relax(self, payload: dict[str, Any], body: str) -> dict[str, Any] | None:
        if "response_format" not in payload:
            return None
        relaxed = dict(payload)
        relaxed.pop("response_format", None)
        return relaxed
