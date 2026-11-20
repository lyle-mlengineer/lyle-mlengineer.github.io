"""ElevenLabs.

Two things make this provider worth keeping: a large catalogue with labels
(gender, accent, age, a written description) and instant voice cloning, which is
how the candidate's own recording becomes the interviewee voice.

Text is requested as raw PCM at 16 kHz and wrapped in a WAV header here, so a
take is one WAV per role and joining is a byte copy. Direction is expressed
through ``voice_settings``: the ``style`` value carries the amount of performance
the delivery notes ask for.
"""

from __future__ import annotations

import httpx

from .audio import join_wav, pcm_to_wav
from .base import Speech, TTSProvider, TTSProviderError, Voice, chunk_text

BASE_URL = "https://api.elevenlabs.io"
MODEL = "eleven_multilingual_v2"
SAMPLE_RATE = 16_000


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    max_chars = 2_500
    supports_clone = True
    supports_direction_tags = False  # tags are only supported by eleven_v3

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        model: str = MODEL,
        timeout_s: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise TTSProviderError(
                "ElevenLabs needs an API key (SKIPPER_ELEVENLABS_API_KEY).", provider=self.name
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self._client = client
        self._catalogue: list[Voice] | None = None

    # -- catalogue ----------------------------------------------------------

    def voices(self) -> list[Voice]:
        if self._catalogue is not None:
            return self._catalogue
        response = self._request("GET", "/v2/voices", params={"page_size": 100})
        if response.status_code >= 400:
            raise TTSProviderError(
                f"ElevenLabs voice list failed (HTTP {response.status_code}).",
                provider=self.name,
                status=response.status_code,
            )
        self._catalogue = [_to_voice(item) for item in response.json().get("voices", [])]
        return self._catalogue

    # -- speech -------------------------------------------------------------

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
        parts = [
            pcm_to_wav(self._speak(piece, voice_id, direction), sample_rate=SAMPLE_RATE)
            for piece in chunks
        ]
        return Speech(
            audio=join_wav(parts),
            chars=len(text),
            voice=voice_id,
            provider=self.name,
            requests=len(chunks),
        )

    def _speak(self, text: str, voice_id: str, direction: list[str] | None) -> bytes:
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": _voice_settings(direction),
        }
        response = self._request(
            "POST",
            f"/v1/text-to-speech/{voice_id}",
            params={"output_format": f"pcm_{SAMPLE_RATE}"},
            json=payload,
        )
        if response.status_code >= 400:
            raise TTSProviderError(
                _message(response, "ElevenLabs could not generate speech."),
                provider=self.name,
                status=response.status_code,
            )
        return response.content

    # -- cloning ------------------------------------------------------------

    def clone_reference(self, path: str, *, name: str = "My voice") -> str:
        with open(path, "rb") as handle:
            audio = handle.read()
        response = self._request(
            "POST",
            "/v1/voices/add",
            data={"name": name[:80], "description": "Reference recording supplied in Skipper."},
            files={"files": ("reference.wav", audio, "audio/wav")},
        )
        if response.status_code >= 400:
            raise TTSProviderError(
                _message(response, "ElevenLabs could not clone that recording."),
                provider=self.name,
                status=response.status_code,
            )
        voice_id = response.json().get("voice_id")
        if not voice_id:
            raise TTSProviderError("ElevenLabs returned no voice id.", provider=self.name)
        return str(voice_id)

    # -- plumbing -----------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {"xi-api-key": self.api_key}
        headers.update(kwargs.pop("headers", {}))
        client = self._client or httpx.Client(timeout=self.timeout_s)
        owns = self._client is None
        try:
            return client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise TTSProviderError(
                f"Could not reach ElevenLabs: {exc}", provider=self.name
            ) from exc
        finally:
            if owns:
                client.close()


def _voice_settings(direction: list[str] | None) -> dict:
    """Direction as settings, since multilingual v2 has no bracket syntax.

    Steadier delivery for technical answers, more style for stories; the tags
    themselves only pick between those two ends.
    """
    words = {word.lower() for word in (direction or [])}
    expressive = bool(words & {"warm", "story", "animated", "bright", "energetic", "narrative"})
    return {
        "stability": 0.4 if expressive else 0.6,
        "similarity_boost": 0.75,
        "style": 0.35 if expressive else 0.1,
        "use_speaker_boost": True,
    }


def _to_voice(item: dict) -> Voice:
    labels = item.get("labels") or {}
    gender = str(labels.get("gender") or "").lower()
    return Voice(
        id=str(item.get("voice_id") or item.get("id") or ""),
        name=str(item.get("name") or "Unnamed voice"),
        provider="elevenlabs",
        description=str(labels.get("description") or labels.get("use_case") or "").replace("_", " "),
        gender=gender if gender in {"male", "female", "neutral"} else "unspecified",
        ethnicity=str(labels.get("ethnicity") or "unspecified"),
        accent=str(labels.get("accent") or ""),
        language=str(labels.get("language") or "en"),
        sample_url=str(item.get("preview_url") or "") or None,
        clonable=str(item.get("category") or "") == "premade",
        tags=tuple(
            str(labels.get(key)) for key in ("age", "use_case") if labels.get(key)
        ),
    )


def _message(response: httpx.Response, fallback: str) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"{fallback} (HTTP {response.status_code})"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict) and detail.get("message"):
        return str(detail["message"])
    if isinstance(detail, str):
        return detail
    return f"{fallback} (HTTP {response.status_code})"
