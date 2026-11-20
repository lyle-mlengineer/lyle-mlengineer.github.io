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
from app.providers.llm.fallback import FallbackLLMProvider
from app.providers.llm.groq import GroqProvider
from app.providers.llm.nvidia import NvidiaProvider
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


class TruncatedStub(LLMProvider):
    name = "stub"
    models = {"large": "stub-large", "small": "stub-small"}

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.budgets: list[int] = []

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.budgets.append(int(kwargs.get("max_tokens") or 0))
        text = self._texts.pop(0) if self._texts else ""
        return LLMResponse(
            text=text,
            model=kwargs.get("model") or "stub-large",
            tokens_in=10,
            tokens_out=5,
            finish_reason="length" if len(self._texts) else "stop",
        )

    def health(self) -> bool:
        return True


def test_complete_json_grows_the_budget_when_a_completion_was_cut_off():
    stub = TruncatedStub(['{"name": "Skip', '{"name": "Skipper"}'])
    payload, _ = stub.complete_json(MESSAGES, SCHEMA, max_tokens=4096)

    assert payload["name"] == "Skipper"
    assert stub.budgets == [4096, 6144]


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


def test_groq_retries_a_truncated_json_answer_with_a_larger_budget():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Failed to generate JSON. See failed_generation.",
                        "type": "invalid_request_error",
                        "code": "json_validate_failed",
                    }
                },
            )
        return _groq_response()

    response = _groq(handler).complete(MESSAGES, response_format="json", max_tokens=6_000)

    assert response.text.startswith("{")
    assert len(seen) == 2
    assert seen[1]["max_completion_tokens"] > seen[0]["max_completion_tokens"]
    assert "closing brace" in seen[1]["messages"][-1]["content"]


def test_groq_marks_an_exhausted_json_retry_as_retryable():
    provider = _groq(
        lambda request: httpx.Response(400, text='{"code": "json_validate_failed"}'),
        max_retries=1,
    )
    with pytest.raises(LLMProviderError) as excinfo:
        provider.complete(MESSAGES, response_format="json", max_tokens=6_000)

    assert excinfo.value.retryable is True
    assert "json_validate_failed" in str(excinfo.value)


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

# ---------------------------------------------------------------- nvidia models


def _nvidia_response(content: str = '{"name": "Skipper"}', model: str = "moonshotai/kimi-k3.1-pro"):
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-nv1",
            "model": model,
            "choices": [
                {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 400, "completion_tokens": 120},
        },
    )


def _nvidia(handler, sleeps=None, **kwargs) -> NvidiaProvider:
    return NvidiaProvider(
        "test-nvidia-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
        jitter=lambda: 0.0,
        tpm=1_000_000,
        **kwargs,
    )


def test_nvidia_sends_the_kimi_payload_with_thinking_off():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _nvidia_response()

    response = _nvidia(handler).complete(MESSAGES, response_format="json")

    payload = json.loads(seen[0].content)
    assert seen[0].url.host == "integrate.api.nvidia.com"
    assert seen[0].url.path == "/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer test-nvidia-key"
    assert payload["model"] == "moonshotai/kimi-k3.1-pro"
    assert payload["max_tokens"] == 4096
    assert "max_completion_tokens" not in payload
    assert payload["reasoning_effort"] == "none"
    assert payload["response_format"] == {"type": "json_object"}
    assert response.tokens_in == 400
    assert response.tokens_out == 120
    assert response.model == "moonshotai/kimi-k3.1-pro"


def test_nvidia_maps_reasoning_effort_onto_deepseek_modes():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _nvidia_response()

    provider = _nvidia(handler)
    for effort, expected in (("max", "max"), ("high", "high"), ("medium", "high"), ("low", "none")):
        provider.complete(MESSAGES, reasoning_effort=effort)
        assert json.loads(seen[-1].content)["reasoning_effort"] == expected


def test_nvidia_retries_without_json_mode_when_the_endpoint_rejects_it():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(400, text="unsupported parameter: response_format")
        return _nvidia_response()

    response = _nvidia(handler).complete(MESSAGES, response_format="json")

    assert response.text.startswith("{")
    assert len(seen) == 2
    first = json.loads(seen[0].content)
    second = json.loads(seen[1].content)
    assert "response_format" in first
    assert "response_format" not in second


def test_nvidia_rejects_empty_completions_with_a_reasoning_hint():
    provider = _nvidia(lambda request: _nvidia_response("   "))
    with pytest.raises(LLMProviderError) as excinfo:
        provider.complete(MESSAGES)
    assert "reasoning" in str(excinfo.value)


def test_nvidia_requires_a_key():
    with pytest.raises(LLMProviderError):
        NvidiaProvider("")


def test_registry_builds_nvidia_with_the_current_free_models(settings):
    settings.llm_provider = "nvidia"
    settings.nvidia_api_key = "nvidia-key"
    settings.llm_model_large = ""
    settings.llm_model_small = ""
    provider = build_llm_provider(settings)

    assert provider.name == "nvidia"
    assert provider.model_for("large") == "moonshotai/kimi-k3.1-pro"
    assert provider.model_for("small") == "nvidia/nemotron-3.5-lightning-30b-a3b"


def test_registry_requires_a_key_for_nvidia(settings):
    settings.llm_provider = "nvidia"
    settings.nvidia_api_key = ""
    with pytest.raises(LLMProviderError):
        build_llm_provider(settings)


def test_resolved_models_follow_the_provider_and_allow_overrides(settings):
    settings.llm_model_large = ""
    settings.llm_model_small = ""
    settings.llm_provider = "groq"
    assert settings.resolved_models() == {
        "large": "openai/gpt-oss-120b",
        "small": "openai/gpt-oss-20b",
    }

    settings.llm_provider = "nvidia"
    assert settings.resolved_models()["small"] == "nvidia/nemotron-3.5-lightning-30b-a3b"

    settings.llm_model_large = "deepseek-ai/deepseek-v4.1-flash"
    assert settings.resolved_models()["large"] == "deepseek-ai/deepseek-v4.1-flash"


def test_nvidia_pricing_is_listed_for_the_ui():
    assert estimate_cost("deepseek-ai/deepseek-v4-flash", 1_000_000, 0) == 0.14
    assert estimate_cost("deepseek-ai/deepseek-v4-pro", 0, 1_000_000) == 3.96


# ---------------------------------------------------------------- oversized strings


def test_complete_json_clamps_an_overlong_string_instead_of_failing():
    schema = {
        "type": "object",
        "required": ["closing"],
        "properties": {"closing": {"type": "string", "max_len": 120}},
    }
    stub = StubLLM([json.dumps({"closing": "I look forward to discussing how my work maps to your team. " * 8})])
    payload, _ = stub.complete_json(MESSAGES, schema)

    assert len(payload["closing"]) <= 120
    assert not payload["closing"].endswith(" ")
    assert len(stub.calls) == 1


# ---------------------------------------------------------------- fallback chain


class FailingLLM(LLMProvider):
    name = "primary"
    models = {"large": "primary-large", "small": "primary-small"}

    def __init__(self, status: int = 429, *, retryable: bool = True) -> None:
        self.status = status
        self.retryable = retryable
        self.calls = 0

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.calls += 1
        raise LLMProviderError("rate limited", status=self.status, retryable=self.retryable)

    def health(self) -> bool:
        return False


class RecordingLLM(LLMProvider):
    name = "secondary"
    models = {"large": "secondary-large", "small": "secondary-small"}

    def __init__(self) -> None:
        self.models_seen: list[str | None] = []

    def complete(self, messages, **kwargs) -> LLMResponse:
        self.models_seen.append(kwargs.get("model"))
        return LLMResponse(text='{"name": "Skipper"}', model=kwargs.get("model") or "secondary-large")

    def health(self) -> bool:
        return True


def test_fallback_switches_to_the_next_provider_and_stays_there():
    primary = FailingLLM()
    secondary = RecordingLLM()
    chain = FallbackLLMProvider([primary, secondary])

    first, _ = chain.complete_json(MESSAGES, SCHEMA)
    second, _ = chain.complete_json(MESSAGES, SCHEMA)

    assert first == second == {"name": "Skipper"}
    assert primary.calls == 1
    assert chain.name == "secondary"
    assert chain.switches == 1


def test_fallback_translates_the_model_tier_for_the_next_provider():
    chain = FallbackLLMProvider([FailingLLM(), RecordingLLM()])
    chain.complete(MESSAGES, model="primary-large")
    assert chain.providers[1].models_seen == ["secondary-large"]


def test_fallback_does_not_move_on_an_auth_error():
    chain = FallbackLLMProvider([FailingLLM(status=401, retryable=False), RecordingLLM()])
    with pytest.raises(LLMProviderError):
        chain.complete(MESSAGES)


def test_registry_chains_the_other_keyed_provider_in_auto_mode(settings):
    settings.llm_provider = "groq"
    settings.groq_api_key = "groq-key"
    settings.nvidia_api_key = "nvidia-key"
    settings.llm_fallbacks = "auto"

    provider = build_llm_provider(settings)

    assert isinstance(provider, FallbackLLMProvider)
    assert [inner.name for inner in provider.providers] == ["groq", "nvidia"]


def test_registry_never_chains_network_providers_around_fake(settings):
    settings.llm_provider = "fake"
    settings.groq_api_key = "groq-key"
    settings.nvidia_api_key = "nvidia-key"
    settings.llm_fallbacks = "auto"

    provider = build_llm_provider(settings)

    assert provider.name == "fake"
    assert not isinstance(provider, FallbackLLMProvider)


def test_nvidia_swaps_a_retired_model_for_the_next_free_endpoint():
    import json

    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if payload["model"] == "deepseek-ai/deepseek-v4-flash":
            return httpx.Response(
                410,
                json={
                    "title": "Gone",
                    "status": 410,
                    "detail": "The model 'deepseek-ai/deepseek-v4-flash' has reached its end of life.",
                },
            )
        return _nvidia_response(model=payload["model"])

    provider = _nvidia(
        handler,
        models={"large": "moonshotai/kimi-k3.1-pro", "small": "deepseek-ai/deepseek-v4-flash"},
        model_fallbacks=(
            "nvidia/nemotron-3.5-lightning-30b-a3b",
            "moonshotai/kimi-k3.1-pro",
        ),
    )

    response = provider.complete(MESSAGES, model="deepseek-ai/deepseek-v4-flash")

    assert [payload["model"] for payload in seen] == [
        "deepseek-ai/deepseek-v4-flash",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
    ]
    assert response.model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert provider.model_for("small") == "nvidia/nemotron-3.5-lightning-30b-a3b"

    # The dead id is remembered: later steps skip straight to the replacement.
    provider.complete(MESSAGES, model="deepseek-ai/deepseek-v4-flash")
    assert seen[-1]["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"


def test_nvidia_treats_404_as_a_retired_model_too():
    import json

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        seen.append(model)
        if model == "gone-model":
            return httpx.Response(404, text="model not found")
        return _nvidia_response(model=model)

    provider = _nvidia(
        handler,
        models={"large": "gone-model", "small": "gone-model"},
        model_fallbacks=("moonshotai/kimi-k3.1-pro",),
    )
    provider.complete(MESSAGES, model="gone-model")

    assert seen == ["gone-model", "moonshotai/kimi-k3.1-pro"]
    assert provider.model_for("large") == "moonshotai/kimi-k3.1-pro"


def test_nvidia_explains_an_exhausted_fallback_chain():
    provider = _nvidia(
        lambda request: httpx.Response(410, text="gone"),
        model_fallbacks=(),
    )
    with pytest.raises(LLMProviderError) as excinfo:
        provider.complete(MESSAGES)
    assert "retired" in str(excinfo.value)
    assert "build.nvidia.com" in str(excinfo.value)


def test_nvidia_drops_reasoning_effort_when_the_endpoint_rejects_it():
    import json

    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if len(seen) == 1:
            return httpx.Response(400, text="unsupported parameter: reasoning_effort")
        return _nvidia_response()

    provider = _nvidia(handler)
    provider.complete(MESSAGES, response_format="json")

    assert seen[0]["reasoning_effort"] == "none"
    assert "reasoning_effort" not in seen[1]
    assert "response_format" in seen[1]
