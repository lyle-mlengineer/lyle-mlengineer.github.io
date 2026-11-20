"""Text-to-speech providers.

The interview pack is read out loud from this layer: one interviewer voice asks
the question, one interviewee voice answers it, and the delivery notes the LLM
wrote become provider-native direction (bracketed tags, or voice settings where
a provider has no tag syntax).

Every provider returns WAV so takes can be concatenated and served without a
transcode step, and every provider declares the two things the UI must know:
how many characters one request accepts, and whether it can clone a reference
recording of the candidate's own voice.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

#: Roughly how long one synthesized request may be, in characters, by default.
DEFAULT_MAX_CHARS = 2_000


class TTSProviderError(RuntimeError):
    """A provider refused or failed a request. The message is user-facing."""

    def __init__(self, message: str, *, provider: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status


@dataclass(frozen=True)
class Voice:
    """A voice the user can pick, described well enough to choose blind."""

    id: str
    name: str
    provider: str
    description: str = ""
    gender: str = "unspecified"  # female|male|neutral|unspecified
    ethnicity: str = "unspecified"
    accent: str = ""
    language: str = "en"
    sample_url: str | None = None
    clonable: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "description": self.description,
            "gender": self.gender,
            "ethnicity": self.ethnicity,
            "accent": self.accent,
            "language": self.language,
            "sample_url": self.sample_url,
            "clonable": self.clonable,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class Speech:
    """One synthesized piece of audio, always WAV in this app."""

    audio: bytes
    chars: int
    voice: str
    provider: str
    requests: int = 1

    @property
    def format(self) -> str:
        return "wav"


class TTSProvider(ABC):
    """Speak text as a named voice.

    ``direction`` is a short list of delivery words the LLM asked for, such as
    ``["confident", "steady"]``. Providers that support bracketed vocal
    directions get them as tags; the rest tune their voice settings instead.
    """

    name: str = "base"
    max_chars: int = DEFAULT_MAX_CHARS
    supports_clone: bool = False
    supports_direction_tags: bool = False

    @abstractmethod
    def voices(self) -> list[Voice]:
        """The catalogue: what this provider can say something in."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        *,
        voice: str,
        direction: list[str] | None = None,
        reference: str | None = None,
    ) -> Speech:
        """Render ``text`` in ``voice``.

        ``reference`` is a path to the candidate's own recording when the
        provider can clone or imitate it; providers without cloning ignore it.
        """

    def clone_reference(self, path: str, *, name: str = "My voice") -> str:
        """Turn a recording into a usable voice id. Raises when unsupported."""
        raise TTSProviderError(
            f"{self.name} cannot clone a reference recording; pick a catalog voice instead.",
            provider=self.name,
        )

    def health(self) -> bool:
        return True

    # -- helpers shared by the concrete providers ---------------------------

    def _tags(self, direction: list[str] | None) -> str:
        if not direction or not self.supports_direction_tags:
            return ""
        words = [word.strip().strip("[]") for word in direction if word.strip()]
        words = [re.sub(r"[^a-zA-Z -]", "", word)[:24].strip() for word in words[:2]]
        words = [word for word in words if word]
        return f"[{' '.join(words)}] " if words else ""


def chunk_text(text: str, limit: int) -> list[str]:
    """Split ``text`` into pieces that each fit one provider request.

    Sentences are the unit, so the parser never breaks mid-clause unless a
    single sentence is longer than the limit — then it falls back to words.
    """
    text = " ".join(text.split())
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            # A "word" longer than the limit (a URL, a run of letters) still has
            # to be sent somewhere, so it is cut at the limit rather than dropped.
            words = [
                sentence[start : start + limit]
                for start in range(0, len(sentence), limit)
            ] if " " not in sentence.strip() else sentence.split()
            piece = ""
            for word in words:
                if len(piece) + len(word) + 1 > limit:
                    if piece:
                        chunks.append(piece)
                    piece = word
                else:
                    piece = f"{piece} {word}".strip()
            if piece:
                chunks.append(piece)
            continue
        if len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks
