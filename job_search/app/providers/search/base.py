"""The search seam.

One result shape regardless of backend. Serper is the primary (Google quality,
needs a key); DuckDuckGo's HTML endpoint is the no-key fallback. Both are wrapped
by an auto provider and a 24-hour cache so a retried run does not re-query.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str
    rank: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResult:
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet", ""),
            provider=data.get("provider", ""),
            rank=int(data.get("rank", 0)),
        )


class SearchProviderError(RuntimeError):
    def __init__(self, message: str, *, provider: str = "", status: int | None = None) -> None:
        self.provider = provider
        self.status = status
        super().__init__(message)


class BudgetExceeded(RuntimeError):
    """The run used all of its search queries."""


class SearchBudget:
    """Per-run query allowance.

    Enforced here rather than in prompts: a model that keeps asking for "one more
    search" gets a deterministic stop instead of an unbounded bill.
    """

    def __init__(self, max_queries: int) -> None:
        self.max_queries = max(0, max_queries)
        self.used = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_queries - self.used)

    def consume(self, count: int = 1) -> None:
        if self.used + count > self.max_queries:
            raise BudgetExceeded(
                f"Search budget exhausted ({self.used}/{self.max_queries} queries used)."
            )
        self.used += count


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        ...

    @abstractmethod
    def health(self) -> bool:
        ...


class BudgetedSearchProvider(SearchProvider):
    """Consumes one query per actual network call, never per cache hit."""

    def __init__(self, inner: SearchProvider, budget: SearchBudget) -> None:
        self.inner = inner
        self.budget = budget
        self.name = inner.name

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        self.budget.consume()
        return self.inner.search(query, limit=limit, recency_days=recency_days)

    def health(self) -> bool:
        return self.inner.health()


def query_hash(query: str, limit: int, recency_days: int | None) -> str:
    raw = f"{query.strip().lower()}|{limit}|{recency_days or 0}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
