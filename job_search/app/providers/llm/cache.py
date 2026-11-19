"""Exact-match LLM cache.

Keyed on everything that changes the answer: provider, model, temperature,
response format and the full message list. This makes retries after a crash free
and keeps development from spending tokens on identical prompts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from sqlalchemy import select

from ...models import LlmCache
from .base import ChatMessage, LLMProvider, LLMResponse


def cache_key(
    provider: str,
    model: str,
    messages: list[ChatMessage],
    temperature: float,
    response_format: str,
) -> str:
    payload = json.dumps(
        {
            "provider": provider,
            "model": model,
            "temperature": round(temperature, 4),
            "format": response_format,
            "messages": [message.as_payload() for message in messages],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingLLMProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, session_factory) -> None:
        self.inner = inner
        self.name = inner.name
        self.models = inner.models
        self._session_factory = session_factory

    def model_for(self, tier: str) -> str:
        return self.inner.model_for(tier)

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
        model = model or self.model_for("large")
        digest = cache_key(self.inner.name, model, messages, temperature, response_format)

        with self._session_factory() as session:
            row = session.scalar(
                select(LlmCache).where(
                    LlmCache.provider == self.inner.name,
                    LlmCache.model == model,
                    LlmCache.prompt_hash == digest,
                )
            )
            if row:
                data = row.response_json
                return LLMResponse(
                    text=data["text"],
                    model=model,
                    tokens_in=0,
                    tokens_out=0,
                    finish_reason="cache",
                    latency_ms=0,
                )

        response = self.inner.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout_s=timeout_s,
            reasoning_effort=reasoning_effort,
        )

        with self._session_factory() as session:
            session.add(
                LlmCache(
                    provider=self.inner.name,
                    model=model,
                    prompt_hash=digest,
                    response_json={"text": response.text},
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                )
            )
            session.commit()
        return response

    def health(self) -> bool:
        return self.inner.health()
