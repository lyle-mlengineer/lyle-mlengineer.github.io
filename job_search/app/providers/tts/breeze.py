"""Breeze Blue.

Breeze keeps the catalogue and the labels (``gender``, ``accent``, ``tone``) on
its own side and returns WAV when asked for it, so the voices the picker shows
are the account's real catalogue rather than a guess. Direction rides in the text
as audio tags, the same way it does for Orpheus.

Cloning is a two-step flow: a clone preview is generated from the upload, then
that preview is saved as a reusable voice. Both steps are done here so the caller
gets one voice id back.
"""

from __future__ import annotations

import httpx

from .base import Speech, TTSProvider, TTSProviderError, Voice, chunk_text

BASE_URL = "https://api.breeze.blue"
DEFAULT_MODEL = "breeze-tts-2"


class BreezeProvider(TTSProvider):
    name = "breeze"
    max_chars = 950  # account default is 1,000 characters per request
    supports_clone = True
    supports_direction_tags = True  # audio tags are part of the input text

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        model: str = DEFAULT_MODEL,
        language: str = "en",
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise TTSProviderError(
                "Breeze needs an API key (SKIPPER_BREEZE_API_KEY).", provider=self.name
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language
        self.timeout_s = timeout_s
        self._client = client
        self._catalogue: list[Voice] | None = None

    def voices(self) -> list[Voice]:
        if self._catalogue is not None:
            return self._catalogue
        response = self._request(
            "GET",
            "/v1/voices",
            params={"language_code": self.language, "voice_type": "default"},
        )
        if response.status_code >= 400:
            raise TTSProviderError(
                f"Breeze voice list failed (HTTP {response.status_code}).",
                provider=self.name,
                status=response.status_code,
            )
        body = response.json()
        rows = body.get("voices") or body.get("data") or []
        self._catalogue = [_to_voice(row) for row in rows if isinstance(row, dict)]
        return self._catalogue

    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        direction: list[str] | None = None,
        reference: str | None = None,
    ) -> Speech:
        voice_id = reference or voice
        chunks = chunk_text(text, self.max_chars)
        if not chunks:
            raise TTSProviderError("Nothing to say.", provider=self.name)
        tags = self._tags(direction)
        parts = [
            self._speak(f"{tags}{piece}" if tags else piece, voice_id, first=index == 0)
            for index, piece in enumerate(chunks)
        ]
        return Speech(
            audio=_join_all(parts),
            chars=len(text),
            voice=voice_id,
            provider=self.name,
            requests=len(chunks),
        )

    def _speak(self, text: str, voice_id: str, *, first: bool) -> bytes:
        payload: dict = {"text": text, "model_id": self.model}
        if first and self.language:
            payload["language_code"] = self.language
        response = self._request(
            "POST",
            f"/v1/text-to-speech/{voice_id}",
            params={"output_format": "wav"},
            json=payload,
        )
        if response.status_code >= 400:
            raise TTSProviderError(
                _message(response, "Breeze could not generate speech."),
                provider=self.name,
                status=response.status_code,
            )
        return response.content

    def clone_reference(self, path: str, *, name: str = "My voice") -> str:
        with open(path, "rb") as handle:
            audio = handle.read()
        preview = self._request(
            "POST",
            "/v1/voice-previews/clone",
            files={"file": ("reference.wav", audio, "audio/wav")},
        )
        if preview.status_code >= 400:
            raise TTSProviderError(
                _message(preview, "Breeze could not analyse that recording."),
                provider=self.name,
                status=preview.status_code,
            )
        generated_id = preview.json().get("generated_voice_id") or preview.json().get("voice_id")
        if not generated_id:
            raise TTSProviderError("Breeze returned no preview id.", provider=self.name)

        saved = self._request(
            "POST",
            f"/v1/voice-previews/{generated_id}/save",
            json={"name": name[:60], "description": "Reference recording supplied in Skipper."},
        )
        if saved.status_code >= 400:
            raise TTSProviderError(
                _message(saved, "Breeze could not save that voice."),
                provider=self.name,
                status=saved.status_code,
            )
        voice_id = saved.json().get("voice_id") or saved.json().get("id") or generated_id
        self._catalogue = None  # the catalogue now has one more voice
        return str(voice_id)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {"xi-api-key": self.api_key}
        headers.update(kwargs.pop("headers", {}))
        client = self._client or httpx.Client(timeout=self.timeout_s)
        owns = self._client is None
        try:
            return client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise TTSProviderError(f"Could not reach Breeze: {exc}", provider=self.name) from exc
        finally:
            if owns:
                client.close()


def _join_all(parts: list[bytes]) -> bytes:
    from .audio import join_wav

    return join_wav(parts)


def _to_voice(item: dict) -> Voice:
    gender = str(item.get("gender") or "").lower()
    tone = item.get("tone") or []
    if isinstance(tone, str):
        tone = [tone]
    accent = str(item.get("accent") or "").replace("_", " ")
    return Voice(
        id=str(item.get("voice_id") or item.get("id") or ""),
        name=str(item.get("name") or item.get("display_name") or "Unnamed voice"),
        provider="breeze",
        description=str(item.get("description") or _describe(accent, tone)),
        gender=gender if gender in {"male", "female", "neutral"} else "unspecified",
        ethnicity=str(item.get("ethnicity") or "unspecified"),
        accent=accent,
        language=str(item.get("language_code") or "en"),
        sample_url=str(item.get("preview_url") or item.get("sample_url") or "") or None,
        clonable=str(item.get("category") or "premade") != "cloned",
        tags=tuple(str(word) for word in tone[:3]),
    )


def _describe(accent: str, tone: list) -> str:
    words = ", ".join(str(word) for word in tone[:3])
    if accent and words:
        return f"{accent.title()} accent, {words}."
    if accent:
        return f"{accent.title()} accent."
    return "Breeze catalog voice."


def _message(response: httpx.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"{fallback} (HTTP {response.status_code})"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str) and detail:
        return detail
    return f"{fallback} (HTTP {response.status_code})"
