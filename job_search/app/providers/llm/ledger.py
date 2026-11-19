"""Per-call ledger.

Runs and steps keep rolling totals, but a total cannot answer "which model, how
long, was it cached, which skill is expensive". This wrapper records every
``complete()`` that happens inside a run step into ``llm_calls``, attributing it
with the call context the pipeline sets before each skill executes.

Recording is best effort: a ledger write that fails must never fail the step that
already paid for the tokens. The exception is logged and the run continues.
"""

from __future__ import annotations

import logging
from typing import Literal

from ...models import LlmCall
from ..call_context import CallContext, call_context, current_call_context
from .base import ChatMessage, LLMProvider, LLMResponse
from .pricing import estimate_cost

logger = logging.getLogger("skipper.llm")

# Backwards-compatible names for the shared context helpers.
llm_call_context = call_context

__all__ = [
    "CallContext",
    "LedgerLLMProvider",
    "call_context",
    "current_call_context",
    "llm_call_context",
]


class LedgerLLMProvider(LLMProvider):
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
        response = self.inner.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout_s=timeout_s,
            reasoning_effort=reasoning_effort,
        )
        self.record(response)
        return response

    def record(self, response: LLMResponse) -> None:
        context = current_call_context()
        if context is None:  # an ad-hoc call outside a run has nothing to bill
            return
        cached = response.finish_reason == "cache"
        row = LlmCall(
            job_id=context.job_id,
            run_id=context.run_id,
            skill=context.skill,
            provider=self.name,
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=estimate_cost(response.model, response.tokens_in, response.tokens_out),
            latency_ms=response.latency_ms,
            cached=cached,
            finish_reason=response.finish_reason,
        )
        try:
            with self._session_factory() as session:
                session.add(row)
                session.commit()
        except Exception:  # pragma: no cover - the run matters more than the ledger
            logger.warning("could not record an LLM call", exc_info=True)

    def health(self) -> bool:
        return self.inner.health()
