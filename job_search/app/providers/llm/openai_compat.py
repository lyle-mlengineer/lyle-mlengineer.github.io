"""Shared transport for OpenAI-compatible chat-completions APIs.

Groq and NVIDIA NIM answer on the same wire format. Only the base URL, the model
names, the token field and the reasoning knob differ, so the retry policy, the
process-local rate limiter and the usage parsing live here once. A vendor module
subclasses this and changes those four things — nothing else.

Timeouts, 429/5xx handling and ``retry-after`` are deliberately identical to the
original Groq implementation: the job runner depends on those semantics.
"""

from __future__ import annotations

import random
import time
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx

from .base import ChatMessage, LLMProvider, LLMProviderError, LLMResponse, estimate_tokens


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


def retry_after_seconds(response: httpx.Response) -> float | None:
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


# Retained under the old private name so existing imports keep working.
_retry_after_seconds = retry_after_seconds


class OpenAICompatibleProvider(LLMProvider):
    """Chat completions over ``POST {base_url}/chat/completions``."""

    vendor = "OpenAI-compatible"
    api_key_env = "SKIPPER_LLM_API_KEY"
    max_tokens_field = "max_completion_tokens"
    #: Sent when the caller does not ask for a specific effort level.
    default_reasoning_effort: str | None = None
    empty_completion_hint = "the step may need a larger token budget"

    def __init__(
        self,
        api_key: str,
        *,
        models: dict[str, str] | None = None,
        base_url: str,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        tpm: int = 30_000,
        client: httpx.Client | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        jitter=random.random,
    ) -> None:
        if not api_key:
            raise LLMProviderError(
                f"{self.api_key_env} is required for the {self.name} provider."
            )
        self.api_key = api_key
        self.models = models or {}
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._jitter = jitter
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_s)
        self._bucket = TokenBucket(tpm, clock=clock, sleep=sleep)

    # ------------------------------------------------------------ vendor hooks

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Skipper/0.1 (job-search agent)",
        }

    def _reasoning_effort(self, requested: str | None, model: str) -> str | None:
        """Map the caller's effort onto this vendor's vocabulary, or drop it."""
        return requested or self.default_reasoning_effort

    def _relax(self, payload: dict[str, Any], body: str) -> dict[str, Any] | None:
        """Return a payload to retry with when a vendor rejects an optional field."""
        return None

    # ------------------------------------------------------------ transport

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
            self.max_tokens_field: max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        effort = self._reasoning_effort(reasoning_effort, model)
        if effort:
            payload["reasoning_effort"] = effort

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
            if response.status_code in {400, 422}:
                relaxed = self._relax(payload, response.text)
                if relaxed is not None:
                    payload = relaxed
                    continue

            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {body}"
                if attempt == attempts - 1:
                    break
                delay = retry_after_seconds(response)
                self._sleep(delay if delay is not None else self._backoff(attempt))
                continue

            raise LLMProviderError(
                f"{self.vendor} returned HTTP {response.status_code}: {body}",
                status=response.status_code,
                retryable=False,
            )

        raise LLMProviderError(
            f"{self.vendor} failed after {attempts} attempts ({last_error}).",
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
            message = choice.get("message") or {}
            text = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            usage = data.get("usage") or {}
            finish_reason = choice.get("finish_reason") or "stop"
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Unreadable {self.vendor} response: {exc}", status=502
            ) from exc

        if not text.strip():
            raise LLMProviderError(
                f"{self.vendor} returned an empty completion ({self.empty_completion_hint}).",
                status=502,
            )
        if reasoning and not text.strip():  # pragma: no cover - defensive ordering
            raise LLMProviderError(
                f"{self.vendor} returned reasoning with no answer ({self.empty_completion_hint}).",
                status=502,
            )
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
