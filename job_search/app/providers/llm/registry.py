"""Build the configured LLM provider.

One function, so routes, the worker and tests all construct the same object.
"""

from __future__ import annotations

import httpx

from ...config import Settings
from ...skills.registry import FAKE_RESPONSES
from .base import LLMProvider, LLMProviderError
from .cache import CachingLLMProvider
from .fake import FakeLLMProvider
from .groq import GroqProvider


def build_llm_provider(
    settings: Settings,
    *,
    session_factory=None,
    client: httpx.Client | None = None,
    sleep=None,
) -> LLMProvider:
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise LLMProviderError(
                "SKIPPER_LLM_PROVIDER=groq requires SKIPPER_GROQ_API_KEY to be set."
            )
        kwargs = {}
        if client is not None:
            kwargs["client"] = client
        if sleep is not None:
            kwargs["sleep"] = sleep
        provider: LLMProvider = GroqProvider(
            settings.groq_api_key,
            models={"large": settings.llm_model_large, "small": settings.llm_model_small},
            base_url=settings.groq_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            tpm=settings.groq_tpm,
            **kwargs,
        )
    elif settings.llm_provider == "fake":
        provider = FakeLLMProvider(FAKE_RESPONSES)
    else:  # pragma: no cover - config validation rejects this
        raise LLMProviderError(f"Unsupported LLM provider: {settings.llm_provider}")

    if session_factory is not None and settings.llm_cache_enabled:
        return CachingLLMProvider(provider, session_factory)
    return provider
