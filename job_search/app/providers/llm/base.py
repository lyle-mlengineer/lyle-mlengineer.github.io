"""The LLM seam.

Skills never import a vendor SDK. They build `ChatMessage` lists and ask for a
validated JSON payload; swapping Groq for OpenAI, OpenRouter or a local vLLM is a
base-URL change in one provider class.

`complete_json` is shared by every provider so parsing, repair and validation
behave identically no matter who is behind the interface.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from ...validation import ValidationError, clamp_lengths, validate

Role = Literal["system", "user", "assistant"]

JSON_INSTRUCTION = (
    "Respond with a single JSON object and nothing else. "
    "No markdown fences, no commentary, no trailing prose."
)

_REPAIR_PROMPT = (
    "That response was not valid for the schema.\n"
    "Errors:\n{errors}\n\n"
    "Return only the corrected JSON object, with every required field present."
)


# ---------------------------------------------------------------- errors


class LLMProviderError(RuntimeError):
    """The provider failed in a way the caller cannot fix by re-prompting."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        self.status = status
        self.retryable = retryable
        super().__init__(message)


class BudgetExceeded(RuntimeError):
    """A run hit its token or query ceiling."""


class SkillValidationError(RuntimeError):
    """The model could not produce a payload that satisfies the skill schema."""

    def __init__(self, message: str, *, errors: list[str] | None = None, raw: str | None = None) -> None:
        self.errors = errors or []
        self.raw = raw
        super().__init__(message)


# ---------------------------------------------------------------- types


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str

    def as_payload(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str = "stop"
    latency_ms: int = 0
    raw: dict | None = field(default=None, repr=False)


class LLMProvider(ABC):
    """A chat-completion provider with explicit tiers, not arbitrary model names."""

    name: str = "base"
    models: dict[str, str] = {}

    @abstractmethod
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
        ...

    @abstractmethod
    def health(self) -> bool:
        ...

    # -- shared behaviour --------------------------------------------------

    def model_for(self, tier: str) -> str:
        try:
            return self.models[tier]
        except KeyError as exc:  # pragma: no cover - configuration error
            raise LLMProviderError(f"Unknown model tier '{tier}' for provider {self.name}") from exc

    def complete_json(
        self,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_s: float = 120.0,
        attempts: int = 2,
        reasoning_effort: str | None = None,
    ) -> tuple[dict[str, Any], LLMResponse]:
        """Call the model, parse, validate, and repair once if needed.

        The second attempt receives the raw assistant output plus the exact
        validation errors, so a near-miss is cheap to fix. Anything still broken
        raises `SkillValidationError` — a step failure, never a silent empty pack.
        """
        convo = list(messages)
        convo.append(ChatMessage("system", JSON_INSTRUCTION + "\n\nSchema:\n" + _schema_hint(schema)))

        last_raw = ""
        last_errors: list[str] = []
        last_validation = "the response was not parseable JSON"
        budget = max_tokens

        for attempt in range(max(1, attempts)):
            response = self.complete(
                convo,
                model=model,
                temperature=temperature,
                max_tokens=budget,
                response_format="json",
                timeout_s=timeout_s,
                reasoning_effort=reasoning_effort,
            )
            last_raw = response.text
            truncated = response.finish_reason == "length"
            try:
                payload = clamp_lengths(json.loads(_strip_json_wrapper(response.text)), schema)
                validate(payload, schema)
                return payload, response
            except json.JSONDecodeError as exc:
                last_errors = [f"$: invalid JSON ({exc.msg} at line {exc.lineno})"]
                last_validation = "the response was not parseable JSON"
                # An unterminated object means the completion was cut off, not
                # that the model wrote nonsense. Re-ask with more room.
                truncated = truncated or exc.pos >= max(0, len(response.text) - 1)
            except ValidationError as exc:
                last_errors = exc.errors
                last_validation = "the JSON did not match the schema"

            if attempt < attempts - 1:
                if truncated:
                    budget = min(32_768, max(budget + 2_048, int(budget * 1.5)))
                convo = [
                    *convo,
                    ChatMessage("assistant", response.text[:6000]),
                    ChatMessage("user", _REPAIR_PROMPT.format(errors="\n".join(last_errors[:12]))),
                ]

        raise SkillValidationError(
            f"Model output failed validation after {attempts} attempts: {last_validation}.",
            errors=last_errors,
            raw=last_raw,
        )


def _schema_hint(schema: dict[str, Any]) -> str:
    text = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
    if len(text) > 4000:
        text = text[:4000] + "…"
    return text


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_json_wrapper(text: str) -> str:
    """Tolerate fences and stray prose around the JSON payload."""
    cleaned = _FENCE.sub("", text.strip())
    if cleaned.lstrip().startswith(("{", "[")):
        return cleaned
    starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
    if not starts:
        return cleaned
    start = min(starts)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end > start:
        return cleaned[start : end + 1]
    return cleaned[start:]


def estimate_tokens(text: str) -> int:
    """Cheap guard for budgets; Groq reports the real number in usage."""
    return max(1, len(text) // 4)
