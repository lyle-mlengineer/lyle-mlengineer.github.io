"""Groq implementation of the LLM seam.

Groq speaks the OpenAI chat-completions wire format, so the only vendor-specific
details here are the base URL, the gpt-oss model names, and Groq's rate limits.
`openai/gpt-oss-*` are reasoning models; requests ask for low reasoning effort by
default and use `max_completion_tokens`, which is the field Groq documents.
"""

from __future__ import annotations

import random
import time
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx

from .base import ChatMessage, LLMProvider, LLMProviderError, LLMResponse, estimate_tokens

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class TokenBucket:
    """Process-local TPM limiter.

    One user, one process, so a per-process bucket is the right scope. It avoids
    the common failure of hammering a free tier until every step 429s.
    """

    def __init__(self, capacity: int, *, clock=time.monotonic, sleep=time.sleep) -> None:
        self.capacity = max(1, capacity)
        self._tokens = float(self.capacity)
        self._updated = clock()
        self._clock = clock
        self._sleep = sleep

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._updated)
        if elapsed:
            self._tokens = min(self.capacity, self._tokens + elapsed * (self.capacity / 60.0))
            self._updated = now

    def acquire(self, amount: int, *, max_wait_s: float = 60.0) -> None:
        wanted = float(min(max(amount, 1), self.capacity))
        waited = 0.0
        while True:
            self._refill()
            if self._tokens >= wanted:
                self._tokens -= wanted
                return
            deficit = wanted - self._tokens
            wait = deficit / (self.capacity / 60.0)
            if waited + wait > max_wait_s:
                raise LLMProviderError(
                    f"Token budget wait of {wait + waited:.0f}s exceeds the {max_wait_s:.0f}s limit.",
                    retryable=False,
                )
            self._sleep(wait)
            waited += wait


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
            return max(0.0, when.timestamp() - time.time())
        except (TypeError, ValueError):
            return None


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str,
        *,
        models: dict[str, str] | None = None,
        base_url: str = GROQ_BASE_URL,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        tpm: int = 30_000,
        client: httpx.Client | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        jitter=random.random,
    ) -> None:
        if not api_key:
            raise LLMProviderError("SKIPPER_GROQ_API_KEY is required for the groq provider.")
        self.api_key = api_key
        self.models = models or {
            "large": "openai/gpt-oss-120b",
            "small": "openai/gpt-oss-20b",
        }
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._jitter = jitter
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_s)
        self._bucket = TokenBucket(tpm, clock=clock, sleep=sleep)

    # ------------------------------------------------------------ transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Skipper/0.1 (job-search agent)",
        }

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Literal["text", "json"] = "text",
        timeout_s: float | None = None,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        model = model or self.model_for("large")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.as_payload() for message in messages],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        if (reasoning_effort or model.startswith("openai/gpt-oss")):
            payload["reasoning_effort"] = reasoning_effort or "low"

        prompt_text = "\n".join(message.content for message in messages)
        self._bucket.acquire(estimate_tokens(prompt_text))

        started = self._clock()
        response = self._post(payload, timeout_s or self.timeout_s)
        latency_ms = int((self._clock() - started) * 1000)
        return self._parse(response, model=model, latency_ms=latency_ms)

    def _post(self, payload: dict[str, Any], timeout_s: float) -> httpx.Response:
        last_error: str = "no attempt made"
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=timeout_s,
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == attempts - 1:
                    break
                self._sleep(self._backoff(attempt))
                continue

            if response.status_code == 200:
                return response

            body = response.text[:300].replace("\n", " ")
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {body}"
                if attempt == attempts - 1:
                    break
                delay = _retry_after_seconds(response)
                self._sleep(delay if delay is not None else self._backoff(attempt))
                continue

            raise LLMProviderError(
                f"Groq returned HTTP {response.status_code}: {body}",
                status=response.status_code,
                retryable=False,
            )

        raise LLMProviderError(
            f"Groq failed after {attempts} attempts ({last_error}).",
            status=429,
            retryable=True,
        )

    def _backoff(self, attempt: int) -> float:
        base = (1.0, 4.0, 12.0)[min(attempt, 2)]
        return base + self._jitter() * 0.5

    def _parse(self, response: httpx.Response, *, model: str, latency_ms: int) -> LLMResponse:
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
            usage = data.get("usage") or {}
            finish_reason = choice.get("finish_reason") or "stop"
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Unreadable Groq response: {exc}", status=502) from exc

        if not text.strip():
            raise LLMProviderError(
                "Groq returned an empty completion (the step may need a larger token budget).",
                status=502,
            )
        if finish_reason == "length":
            # Keep the text: a truncated JSON payload fails validation and is repaired,
            # but the caller should see the reason in the run ledger.
            pass
        return LLMResponse(
            text=text,
            model=data.get("model") or model,
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            raw={"id": data.get("id"), "usage": usage},
        )

    def health(self) -> bool:
        try:
            response = self._client.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=5.0,
            )
            return response.status_code < 400
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
