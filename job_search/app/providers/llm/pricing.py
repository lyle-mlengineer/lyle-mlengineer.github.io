"""Approximate token pricing, for the run cost line in the UI.

Numbers are per million tokens and are only used for display; they are not a
billing source of truth. Override them in code if Groq changes its rates.
"""

from __future__ import annotations

# USD per 1M tokens: (input, output)
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.075, 0.30),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return round((tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out, 6)
