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
from .fallback import FallbackLLMProvider
from .groq import GroqProvider
from .ledger import LedgerLLMProvider
from .nvidia import NvidiaProvider
from .openrouter import OpenRouterProvider


def _vendor_provider(
    name: str,
    settings: Settings,
    *,
    session_factory=None,
    client: httpx.Client | None = None,
    sleep=None,
) -> LLMProvider:
    models = settings.models_for(name, generic=(name == settings.llm_provider))
    kwargs = {}
    if client is not None:
        kwargs["client"] = client
    if sleep is not None:
        kwargs["sleep"] = sleep

    if name == "groq":
        if not settings.groq_api_key:
            raise LLMProviderError(
                "SKIPPER_LLM_PROVIDER=groq requires SKIPPER_GROQ_API_KEY to be set."
            )
        return GroqProvider(
            settings.groq_api_key,
            models=models,
            base_url=settings.groq_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            tpm=settings.groq_tpm,
            **kwargs,
        )
    if name == "nvidia":
        if not settings.nvidia_api_key:
            raise LLMProviderError(
                "SKIPPER_LLM_PROVIDER=nvidia requires SKIPPER_NVIDIA_API_KEY to be set."
            )
        return NvidiaProvider(
            settings.nvidia_api_key,
            models=models,
            base_url=settings.nvidia_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            tpm=settings.nvidia_tpm,
            reasoning_effort=settings.nvidia_reasoning_effort,
            model_fallbacks=settings.nvidia_model_fallback_list,
            **kwargs,
        )
    if name == "openrouter":
        if not settings.openrouter_api_key:
            raise LLMProviderError(
                "SKIPPER_LLM_PROVIDER=openrouter requires SKIPPER_OPENROUTER_API_KEY to be set."
            )
        return OpenRouterProvider(
            settings.openrouter_api_key,
            models=models,
            base_url=settings.openrouter_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            tpm=settings.openrouter_tpm,
            referer=settings.openrouter_referer,
            title=settings.openrouter_title,
            **kwargs,
        )
    if name == "fake":
        return FakeLLMProvider(FAKE_RESPONSES)
    raise LLMProviderError(f"Unsupported LLM provider: {name}")


def build_llm_provider(
    settings: Settings,
    *,
    session_factory=None,
    client: httpx.Client | None = None,
    sleep=None,
) -> LLMProvider:
    primary = _vendor_provider(
        settings.llm_provider,
        settings,
        session_factory=session_factory,
        client=client,
        sleep=sleep,
    )

    chain = [primary]
    for name in settings.fallback_providers:
        chain.append(
            _vendor_provider(
                name,
                settings,
                session_factory=session_factory,
                client=client,
                sleep=sleep,
            )
        )
    provider: LLMProvider = FallbackLLMProvider(chain) if len(chain) > 1 else primary

    if session_factory is not None:
        if settings.llm_cache_enabled:
            provider = CachingLLMProvider(provider, session_factory)
        provider = LedgerLLMProvider(provider, session_factory)
    return provider
