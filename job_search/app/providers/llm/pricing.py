"""Approximate token pricing, for the run cost line and the resources dashboard.

Numbers are per million tokens and are only used for display; they are not a
billing source of truth. Override them in code if a provider changes its rates.
A model that is not listed costs zero in the UI — never invent a price.
"""

from __future__ import annotations

# USD per 1M tokens: (input, output)
PRICES: dict[str, tuple[float, float]] = {
    # Groq
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.075, 0.30),
    # NVIDIA NIM — DeepSeek
    "deepseek-ai/deepseek-v4-pro": (1.32, 3.96),
    "deepseek-ai/deepseek-v4-flash": (0.14, 0.28),
    "deepseek-ai/deepseek-v4-flash-0731": (0.14, 0.28),
    "deepseek-ai/deepseek-r1": (0.55, 2.19),
    "deepseek-ai/deepseek-v3.1": (0.28, 0.42),
}

# Fake/test models are free by design; listing them keeps the UI honest.
PRICES.update({"fake-large": (0.0, 0.0), "fake-small": (0.0, 0.0)})


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return round((tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out, 6)
