"""Build the configured LLM provider.

One function, so routes, the worker and tests all construct the same object:

    vendor provider -> exact-match cache -> call ledger

The ledger is outermost so cache hits are recorded too (with zero tokens) and the
resources dashboard can tell "free" from "never called".
"""

from __future__ import annotations

import httpx

from ...config import Settings
from ...skills.registry import FAKE_RESPONSES
from .base import LLMProvider, LLMProviderError
from .cache import CachingLLMProvider
from .fake import FakeLLMProvider
from .groq import GroqProvider
from .ledger import LedgerLLMProvider
from .nvidia import NvidiaProvider


def build_llm_provider(
    settings: Settings,
    *,
    session_factory=None,
    client: httpx.Client | None = None,
    sleep=None,
) -> LLMProvider:
    models = settings.resolved_models()
    kwargs = {}
    if client is not None:
        kwargs["client"] = client
    if sleep is not None:
        kwargs["sleep"] = sleep

    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise LLMProviderError(
                "SKIPPER_LLM_PROVIDER=groq requires SKIPPER_GROQ_API_KEY to be set."
            )
        provider: LLMProvider = GroqProvider(
            settings.groq_api_key,
            models=models,
            base_url=settings.groq_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            tpm=settings.groq_tpm,
            **kwargs,
        )
    elif settings.llm_provider == "nvidia":
        if not settings.nvidia_api_key:
            raise LLMProviderError(
                "SKIPPER_LLM_PROVIDER=nvidia requires SKIPPER_NVIDIA_API_KEY to be set."
            )
        provider = NvidiaProvider(
            settings.nvidia_api_key,
            models=models,
            base_url=settings.nvidia_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            tpm=settings.nvidia_tpm,
            reasoning_effort=settings.nvidia_reasoning_effort,
            **kwargs,
        )
    elif settings.llm_provider == "fake":
        provider = FakeLLMProvider(FAKE_RESPONSES)
    else:  # pragma: no cover - config validation rejects this
        raise LLMProviderError(f"Unsupported LLM provider: {settings.llm_provider}")

    if session_factory is not None:
        if settings.llm_cache_enabled:
            provider = CachingLLMProvider(provider, session_factory)
        provider = LedgerLLMProvider(provider, session_factory)
    return provider
