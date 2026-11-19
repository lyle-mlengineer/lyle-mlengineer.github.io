"""Approximate web-search pricing, for the resources dashboard.

Serper bills per query (its plans work out to about $0.001 per search); the
DuckDuckGo fallback is free. Like the LLM prices these are display estimates, not
a bill, and an unknown provider is priced at zero rather than guessed.
"""

from __future__ import annotations

# USD per query.
SEARCH_PRICES: dict[str, float] = {
    "serper": 0.001,
    "duckduckgo": 0.0,
    "auto": 0.001,
    "fake": 0.0,
}


def estimate_search_cost(provider: str, *, cached: bool = False) -> float:
    if cached:
        return 0.0
    return SEARCH_PRICES.get(provider, 0.0)
