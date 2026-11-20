"""What speech costs, per million characters.

These are published list prices turned into a single number so the resources
dashboard can show speech next to chat and search. They are estimates, not
billing: plans, discounts and plan tiers move the real number, and a provider
with no published price is recorded as zero rather than guessed.

* Orpheus v1 English on Groq — $22 / 1M characters (published).
* ElevenLabs multilingual v2 — about $100 / 1M characters at the Creator tier,
  which is a ceiling; the free and starter tiers include fewer characters.
* Breeze — the account's plan decides it, so no per-character price is assumed.
"""

from __future__ import annotations

TTS_PRICES: dict[str, float] = {
    "orpheus": 22.0,
    "elevenlabs": 100.0,
    "breeze": 0.0,
    "fake": 0.0,
}

#: Providers whose price is a real published figure rather than zero-by-default.
PRICED_PROVIDERS = frozenset({"orpheus", "elevenlabs"})


def speech_cost(provider: str, chars: int) -> float:
    """Estimated dollars for ``chars`` characters of speech."""
    if chars <= 0:
        return 0.0
    return round(chars / 1_000_000 * TTS_PRICES.get(provider, 0.0), 6)


def is_priced(provider: str) -> bool:
    return provider in PRICED_PROVIDERS
