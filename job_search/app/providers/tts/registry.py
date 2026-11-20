"""TTS composition: pick a provider from settings and search its voices.

``auto`` prefers whichever service the environment already has a key for, in the
order ElevenLabs (cloning), Breeze (catalogue + tags), Orpheus (cheap, no clone).
With no key at all it falls back to the offline provider, so a fresh clone of the
repo can still generate a take and play it.
"""

from __future__ import annotations

from ...config import Settings
from .base import TTSProvider, TTSProviderError, Voice
from .breeze import BreezeProvider
from .elevenlabs import ElevenLabsProvider
from .fake import FakeTTSProvider
from .orpheus import OrpheusProvider

PROVIDER_LABELS = {
    "fake": "Offline tones",
    "orpheus": "Orpheus on Groq",
    "elevenlabs": "ElevenLabs",
    "breeze": "Breeze Blue",
}

PROVIDER_NOTES = {
    "fake": "No key needed. Generates tones so the flow can be exercised offline.",
    "orpheus": "$22 per million characters, vocal direction tags, no voice cloning.",
    "elevenlabs": "Large labelled catalogue and instant cloning of your own voice.",
    "breeze": "Catalogue with tone labels and two-step voice cloning.",
}


def build_tts_provider(settings: Settings, **kwargs) -> TTSProvider:
    choice = settings.tts_provider
    if choice == "fake":
        return FakeTTSProvider()
    if choice == "orpheus":
        return OrpheusProvider(
            settings.groq_api_key,
            base_url=settings.groq_base_url,
            timeout_s=settings.tts_timeout_s,
            **kwargs,
        )
    if choice == "elevenlabs":
        return ElevenLabsProvider(
            settings.elevenlabs_api_key, timeout_s=settings.tts_timeout_s, **kwargs
        )
    if choice == "breeze":
        return BreezeProvider(
            settings.breeze_api_key, timeout_s=settings.tts_timeout_s, **kwargs
        )

    # auto
    if settings.elevenlabs_api_key:
        return ElevenLabsProvider(
            settings.elevenlabs_api_key, timeout_s=settings.tts_timeout_s, **kwargs
        )
    if settings.breeze_api_key:
        return BreezeProvider(settings.breeze_api_key, timeout_s=settings.tts_timeout_s, **kwargs)
    if settings.groq_api_key:
        return OrpheusProvider(
            settings.groq_api_key,
            base_url=settings.groq_base_url,
            timeout_s=settings.tts_timeout_s,
            **kwargs,
        )
    return FakeTTSProvider()


def search_voices(
    voices: list[Voice],
    *,
    query: str = "",
    gender: str = "",
    ethnicity: str = "",
    clonable_only: bool = False,
) -> list[Voice]:
    """Filter the catalogue the way the picker's controls do.

    The query is matched against every human-readable field, so "calm female" or
    "american" both work without a separate index.
    """
    needle = query.strip().lower()
    gender_wanted = gender.strip().lower()
    ethnicity_wanted = ethnicity.strip().lower()
    out: list[Voice] = []
    for voice in voices:
        if gender_wanted and voice.gender.lower() != gender_wanted:
            continue
        if ethnicity_wanted and voice.ethnicity.lower() != ethnicity_wanted:
            continue
        if clonable_only and not voice.clonable:
            continue
        if needle:
            haystack = " ".join(
                [
                    voice.name,
                    voice.description,
                    voice.accent,
                    voice.gender,
                    voice.ethnicity,
                    voice.language,
                    " ".join(voice.tags),
                ]
            ).lower()
            if needle not in haystack:
                continue
        out.append(voice)
    return out


def catalogue(provider: TTSProvider) -> list[Voice]:
    """Every voice a provider offers, or an empty list if it cannot be reached."""
    try:
        return provider.voices()
    except TTSProviderError:
        return []


__all__ = [
    "PROVIDER_LABELS",
    "PROVIDER_NOTES",
    "build_tts_provider",
    "catalogue",
    "search_voices",
]
