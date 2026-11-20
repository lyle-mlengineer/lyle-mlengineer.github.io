"""Provider failover.

A free tier answers most calls and rate-limits the rest. Instead of failing a
run on the first 429, the pipeline talks to a chain: the configured primary,
then every other hosted provider whose key is present. A retryable failure
(429, 5xx, exhausted retries, quota) moves to the next provider for that call
and stays there for the rest of the process, so a run does not pay the retry
window again on every step.

The wrapper maps the requested model back to its tier before asking the next
provider, because ``moonshotai/kimi-k3.1-pro`` means nothing to Groq. Skills
ask for a tier through ``model_for()``, and each provider keeps its own model
ids from ``DEFAULT_LLM_MODELS``.

Ordering is intentional: the primary is always first, the network providers are
never mixed with ``fake`` (tests and the offline default must stay offline), and
a provider without a key is skipped rather than raising at call time.
"""

from __future__ import annotations

import logging
from typing import Literal

from .base import ChatMessage, LLMProvider, LLMProviderError, LLMResponse

logger = logging.getLogger("skipper.llm")


def should_fail_over(exc: LLMProviderError) -> bool:
    """Only errors another vendor can plausibly fix move the chain forward."""
    if exc.retryable:
        return True
    return exc.status == 429 or exc.status == 402 or (exc.status or 0) >= 500


class FallbackLLMProvider(LLMProvider):
    """Try the active provider, then the rest of the chain, and stay switched."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackLLMProvider needs at least one provider")
        self.providers = list(providers)
        self._active = 0
        self._switches = 0

    @property
    def name(self) -> str:
        return self.providers[self._active].name

    @property
    def models(self) -> dict[str, str]:
        return self.providers[self._active].models

    @property
    def active(self) -> LLMProvider:
        return self.providers[self._active]

    @property
    def switches(self) -> int:
        return self._switches

    def model_for(self, tier: str) -> str:
        return self.active.model_for(tier)

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Literal["text", "json"] = "text",
        timeout_s: float = 120.0,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        tier = self._tier_for(model)
        start = self._active
        count = len(self.providers)
        last_error: LLMProviderError | None = None

        for offset in range(count):
            index = (start + offset) % count
            provider = self.providers[index]
            target = provider.model_for(tier) if tier else model
            try:
                response = provider.complete(
                    messages,
                    model=target,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout_s=timeout_s,
                    reasoning_effort=reasoning_effort,
                )
            except LLMProviderError as exc:
                if not should_fail_over(exc) or offset == count - 1:
                    raise
                last_error = exc
                next_name = self.providers[(index + 1) % count].name
                logger.warning(
                    "%s failed (%s); switching to %s for this run",
                    provider.name,
                    exc,
                    next_name,
                )
                continue

            if index != self._active:
                self._active = index
                self._switches += 1
                logger.warning("LLM provider switched to %s", provider.name)
            return response

        # Unreachable: the final provider re-raises. Kept for type checkers.
        raise last_error or LLMProviderError("Every LLM provider failed.", retryable=True)

    def _tier_for(self, model: str | None) -> str | None:
        """Map a concrete model id back to the tier the skill asked for."""
        if not model:
            return None
        for provider in self.providers:
            for tier, value in provider.models.items():
                if value == model:
                    return tier
        return None

    def health(self) -> bool:
        return any(provider.health() for provider in self.providers)

    def close(self) -> None:
        for provider in self.providers:
            close = getattr(provider, "close", None)
            if close is not None:
                close()
