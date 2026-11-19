"""Deterministic provider used by tests and by the default dev configuration.

Responses are keyed by a marker in the conversation — a skill name is enough.
This keeps the whole app runnable with no API key and makes the e2e pipeline
testable without network access.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from .base import ChatMessage, LLMProvider, LLMResponse, estimate_tokens


class FakeLLMProvider(LLMProvider):
    name = "fake"
    models = {"large": "fake-large", "small": "fake-small"}

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        *,
        default_json: Any = None,
        default_text: str = "Fake completion.",
    ) -> None:
        self.responses = dict(responses or {})
        self.default_json = default_json if default_json is not None else {"ok": True}
        self.default_text = default_text
        self.calls: list[dict[str, Any]] = []

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
        convo = "\n".join(f"[{message.role}] {message.content}" for message in messages)
        self.calls.append(
            {
                "model": model,
                "response_format": response_format,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "conversation": convo,
            }
        )

        text = self._match(convo)
        if text is None:
            text = json.dumps(self.default_json) if response_format == "json" else self.default_text

        return LLMResponse(
            text=text,
            model=model,
            tokens_in=estimate_tokens(convo),
            tokens_out=estimate_tokens(text),
            finish_reason="stop",
            latency_ms=1,
        )

    def _match(self, conversation: str) -> str | None:
        for marker, response in self.responses.items():
            if marker in conversation:
                return response
        return None

    def health(self) -> bool:
        return True
