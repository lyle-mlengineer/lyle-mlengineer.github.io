"""Offline TTS: the default provider in development and in every test.

It speaks in short tones whose pitch follows the voice, which is enough to
prove the take was generated, joined and served. It honours the same contract as
the hosted providers — chunking, direction tags, cloning — so the interview
audio flow can be exercised with no key and no network.
"""

from __future__ import annotations

from pathlib import Path

from .audio import join_wav, tone_wav
from .base import Speech, TTSProvider, Voice, chunk_text

_VOICES: tuple[Voice, ...] = (
    Voice(
        id="fake-interviewer",
        name="Mara",
        provider="fake",
        description="Even, unhurried interviewer who asks one question at a time.",
        gender="female",
        ethnicity="unspecified",
        accent="Neutral English",
        tags=("warm", "clear"),
    ),
    Voice(
        id="fake-interviewer-alt",
        name="Oskar",
        provider="fake",
        description="Low, level voice; sounds like a hiring manager with minutes to spare.",
        gender="male",
        ethnicity="unspecified",
        accent="Neutral English",
        tags=("calm", "dry"),
    ),
    Voice(
        id="fake-answerer",
        name="Junie",
        provider="fake",
        description="Bright, conversational read that keeps long answers listenable.",
        gender="female",
        ethnicity="unspecified",
        accent="Neutral English",
        tags=("warm", "confident"),
    ),
    Voice(
        id="fake-answerer-alt",
        name="Nate",
        provider="fake",
        description="Measured, slightly quick delivery for technical walkthroughs.",
        gender="male",
        ethnicity="unspecified",
        accent="Neutral English",
        tags=("focused", "steady"),
    ),
)

_PITCH = {
    "fake-interviewer": 200.0,
    "fake-interviewer-alt": 140.0,
    "fake-answerer": 240.0,
    "fake-answerer-alt": 170.0,
}


class FakeTTSProvider(TTSProvider):
    name = "fake"
    max_chars = 190
    supports_clone = True
    supports_direction_tags = True

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.clones: list[str] = []

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
        if not text.strip():
            raise ValueError("nothing to speak")
        chunks = chunk_text(text, self.max_chars)
        pitch = _PITCH.get(reference or voice, 210.0)
        parts = [
            tone_wav(min(1.2, max(0.08, len(chunk) / 90)), frequency=pitch + 6 * index)
            for index, chunk in enumerate(chunks)
        ]
        self.calls.append(
            {
                "voice": reference or voice,
                "chars": len(text),
                "requests": len(chunks),
                "direction": list(direction or []),
            }
        )
        return Speech(
            audio=join_wav(parts),
            chars=len(text),
            voice=reference or voice,
            provider=self.name,
            requests=len(chunks),
        )

    def clone_reference(self, path: str, *, name: str = "My voice") -> str:
        if not Path(path).exists():
            raise FileNotFoundError(path)
        voice_id = "fake-reference"
        if voice_id not in self.clones:
            self.clones.append(voice_id)
        return voice_id
