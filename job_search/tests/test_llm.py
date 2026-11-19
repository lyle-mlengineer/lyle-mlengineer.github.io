from __future__ import annotations

import json

import httpx
import pytest

from app.db import get_session_factory
from app.providers.llm.base import (
    ChatMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    SkillValidationError,
)
from app.providers.llm.cache import CachingLLMProvider
from app.providers.llm.fake import FakeLLMProvider
from app.providers.llm.groq import GroqProvider
from app.providers.llm.pricing import estimate_cost
from app.providers.llm.registry import build_llm_provider

SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string", "min_len": 2}},
}
MESSAGES = [ChatMessage("user", "skill: job_summary summarize this role")]


class StubLLM(LLMProvider):
    name = "stub"
    models = {"large": "stub-large", "small": "stub-small"}

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls: list[list[ChatMessage]] = []

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.calls.append(list(messages))
        text = self._texts.pop(0) if self._texts else ""
        return LLMResponse(text=text, model=kwargs.get("model") or "stub-large", tokens_in=10, tokens_out=5)

    def health(self) -> bool:
        return True


# ---------------------------------------------------------------- fake provider


def test_fake_provider_is_deterministic_and_tagged():
    fake = FakeLLMProvider({"job_summary": '{"name": "summary"}'})
    payload, response = fake.complete_json(MESSAGES, SCHEMA)
    assert payload == {"name": "summary"}
    assert response.model == "fake-large"
    assert fake.calls[0]["response_format"] == "json"


def test_fake_provider_returns_default_json_for_unknown_prompts():
    fake = FakeLLMProvider(default_json={"ok": True})
    payload, _ = fake.complete_json([ChatMessage("user", "unmatched")], {"type": "object"})
    assert payload == {"ok": True}


# ---------------------------------------------------------------- complete_json


def test_complete_json_accepts_fenced_output():
    stub = StubLLM(['```json\n{"name": "Skipper"}\n```'])
    payload, _ = stub.complete_json(MESSAGES, SCHEMA)
    assert payload["name"] == "Skipper"
    assert len(stub.calls) == 1
    assert "Schema:" in stub.calls[0][-1].content


def test_complete_json_repairs_once_and_names_the_errors():
    stub = StubLLM(["I think the name is Skipper.", '{"name": "Skipper"}'])
    payload, _ = stub.complete_json(MESSAGES, SCHEMA)

    assert payload["name"] == "Skipper"
    assert len(stub.calls) == 2
    repair_turn = stub.calls[1][-1].content
    assert "not valid" in repair_turn
    assert "invalid JSON" in repair_turn


def test_complete_json_raises_when_repair_also_fails():
    stub = StubLLM(['{"name": ""}', "still not json"])
    with pytest.raises(SkillValidationError) as excinfo:
        stub.complete_json(MESSAGES, SCHEMA)

    assert excinfo.value.errors
    assert "after 2 attempts" in str(excinfo.value)
    assert excinfo.value.raw == "still not json"


def test_complete_json_strips_surrounding_prose():
    stub = StubLLM(['Here you go:\n{"name": "Skipper"}\nHope that helps.'])
    payload, _ = stub.complete_json(MESSAGES, SCHEMA)
    assert payload["name"] == "Skipper"


# ---------------------------------------------------------------- groq


def _groq_response(content: str = '{"name": "Skipper"}') -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        },
    )


def _groq(handler, sleeps=None, **kwargs) -> GroqProvider:
    return GroqProvider(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
        jitter=lambda: 0.0,
        tpm=1_000_000,
        **kwargs,
    )


def test_groq_sends_the_expected_payload_and_reads_usage():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _groq_response()

    provider = _groq(handler)
    response = provider.complete(MESSAGES, response_format="json")

    payload = json.loads(seen[0].content)
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["reasoning_effort"] == "low"
    assert payload["max_completion_tokens"] == 4096
    assert seen[0].headers["authorization"] == "Bearer test-key"
    assert response.tokens_in == 120
    assert response.tokens_out == 30
    assert response.finish_reason == "stop"


def test_groq_honours_retry_after_on_429():
    seen: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(429, headers={"retry-after": "2"}, text="slow down")
        return _groq_response()

    provider = _groq(handler, sleeps=sleeps)
    response = provider.complete(MESSAGES)

    assert response.text.startswith("{")
    assert sleeps == [2.0]
    assert len(seen) == 2


def test_groq_retries_5xx_with_backoff_then_succeeds():
    seen: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) < 3:
            return httpx.Response(503, text="unavailable")
        return _groq_response()

    provider = _groq(handler, sleeps=sleeps)
    provider.complete(MESSAGES)
    assert sleeps == [1.0, 4.0]


def test_groq_does_not_retry_auth_errors():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, text="bad key")

    provider = _groq(handler)
    with pytest.raises(LLMProviderError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.status == 401
    assert len(seen) == 1


def test_groq_gives_up_after_max_retries():
    sleeps: list[float] = []
    provider = _groq(lambda request: httpx.Response(500, text="boom"), sleeps=sleeps, max_retries=1)
    with pytest.raises(LLMProviderError) as excinfo:
        provider.complete(MESSAGES)
    assert excinfo.value.retryable is True
    assert sleeps == [1.0]


def test_groq_rejects_empty_completions():
    provider = _groq(lambda request: _groq_response("   "))
    with pytest.raises(LLMProviderError):
        provider.complete(MESSAGES)


def test_groq_health_uses_the_models_endpoint():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"data": []})

    assert _groq(handler).health() is True
    assert paths == ["/openai/v1/models"]


def test_pricing_estimates_cost_from_usage():
    assert estimate_cost("openai/gpt-oss-120b", 1_000_000, 0) == 0.15
    assert estimate_cost("unknown-model", 1000, 1000) == 0.0


# ---------------------------------------------------------------- registry


def test_registry_builds_fake_provider_without_keys(settings):
    provider = build_llm_provider(settings)
    assert provider.name == "fake"


def test_registry_requires_a_key_for_groq(settings):
    settings.llm_provider = "groq"
    settings.groq_api_key = ""
    with pytest.raises(LLMProviderError):
        build_llm_provider(settings)


# ---------------------------------------------------------------- cache


def test_llm_cache_returns_the_first_response(client, settings):
    stub = StubLLM(['{"name": "Skipper"}'])
    cached = CachingLLMProvider(stub, get_session_factory(settings))

    first, _ = cached.complete_json(MESSAGES, SCHEMA)
    second, response = cached.complete_json(MESSAGES, SCHEMA)

    assert first == second == {"name": "Skipper"}
    assert len(stub.calls) == 1
    assert response.finish_reason == "cache"
    assert response.tokens_in == 0


def test_llm_cache_key_includes_temperature(client, settings):
    stub = StubLLM(['{"name": "Skipper"}', '{"name": "Skipper"}'])
    cached = CachingLLMProvider(stub, get_session_factory(settings))

    cached.complete(MESSAGES, temperature=0.2)
    cached.complete(MESSAGES, temperature=0.9)

    assert len(stub.calls) == 2