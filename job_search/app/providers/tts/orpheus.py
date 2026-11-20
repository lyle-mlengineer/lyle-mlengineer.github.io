"""Orpheus v1 English, served by Groq.

Groq's speech endpoint is OpenAI-shaped (``POST /audio/speech``) and the only
format Orpheus returns is WAV, which is exactly what takes are joined from.
Each request accepts 200 characters, so long answers are split into sentences
and each piece carries the direction tags: forgetting them on later chunks
would change the delivery mid-answer.
"""

from __future__ import annotations

import time

import httpx

from .audio import join_wav
from .base import Speech, TTSProvider, TTSProviderError, Voice, chunk_text

MODEL = "canopylabs/orpheus-v1-english"

_VOICES: tuple[Voice, ...] = (
    Voice(
        id="hannah",
        name="Hannah",
        provider="orpheus",
        description="Clear, friendly and mid-paced — the safest interviewer read.",
        gender="female",
        ethnicity="unspecified",
        accent="US English",
        tags=("warm", "clear"),
    ),
    Voice(
        id="autumn",
        name="Autumn",
        provider="orpheus",
        description="Bright and quick; suits short questions and energetic answers.",
        gender="female",
        ethnicity="unspecified",
        accent="US English",
        tags=("bright", "quick"),
    ),
    Voice(
        id="diana",
        name="Diana",
        provider="orpheus",
        description="Lower, more deliberate; reads technical answers without rushing.",
        gender="female",
        ethnicity="unspecified",
        accent="US English",
        tags=("calm", "measured"),
    ),
    Voice(
        id="daniel",
        name="Daniel",
        provider="orpheus",
        description="Steady interviewer voice with a slight downward fall at questions.",
        gender="male",
        ethnicity="unspecified",
        accent="US English",
        tags=("steady", "dry"),
    ),
    Voice(
        id="austin",
        name="Austin",
        provider="orpheus",
        description="Plain, unfussy and easy to follow for long walkthroughs.",
        gender="male",
        ethnicity="unspecified",
        accent="US English",
        tags=("plain", "even"),
    ),
    Voice(
        id="troy",
        name="Troy",
        provider="orpheus",
        description="Confident and a touch formal; good for behavioural answers.",
        gender="male",
        ethnicity="unspecified",
        accent="US English",
        tags=("confident", "formal"),
    ),
)


class OrpheusProvider(TTSProvider):
    name = "orpheus"
    max_chars = 190  # Groq rejects more than 200 characters per request
    supports_clone = False
    supports_direction_tags = True

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise TTSProviderError(
                "Orpheus needs a Groq API key (SKIPPER_GROQ_API_KEY).", provider=self.name
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._client = client

    def voices(self) -> list[Voice]:
        return list(_VOICES)

    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        direction: list[str] | None = None,
        reference: str | None = None,
    ) -> Speech:
        known = {item.id for item in _VOICES}
        if voice not in known:
            raise TTSProviderError(f"Orpheus has no voice called {voice!r}.", provider=self.name)
        chunks = chunk_text(text, self.max_chars)
        if not chunks:
            raise TTSProviderError("Nothing to say.", provider=self.name)

        tags = self._tags(direction)
        parts = [self._speak(f"{tags}{piece}", voice) for piece in chunks]
        return Speech(
            audio=join_wav(parts),
            chars=len(text),
            voice=voice,
            provider=self.name,
            requests=len(chunks),
        )

    def _speak(self, text: str, voice: str) -> bytes:
        payload = {
            "model": MODEL,
            "input": text[:200],
            "voice": voice,
            "response_format": "wav",
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/audio/speech"
        response = self._post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            raise TTSProviderError(
                _message(response, "Groq could not generate speech."),
                provider=self.name,
                status=response.status_code,
            )
        return response.content

    def _post(self, url: str, **kwargs) -> httpx.Response:
        client = self._client or httpx.Client(timeout=self.timeout_s)
        owns = self._client is None
        try:
            for attempt in range(3):
                response = client.post(url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 2:
                        return response
                    time.sleep(_retry_after(response))
                    continue
                return response
            return response  # pragma: no cover - loop always returns
        except httpx.HTTPError as exc:
            raise TTSProviderError(f"Could not reach Groq: {exc}", provider=self.name) from exc
        finally:
            if owns:
                client.close()

    def health(self) -> bool:
        return True


def _retry_after(response: httpx.Response) -> float:
    try:
        return min(8.0, max(0.5, float(response.headers.get("retry-after", "1"))))
    except ValueError:
        return 1.0


def _message(response: httpx.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"{fallback} (HTTP {response.status_code})"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return f"{fallback} (HTTP {response.status_code})"
