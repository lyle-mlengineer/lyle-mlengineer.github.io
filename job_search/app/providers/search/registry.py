"""Search composition: auto fallback, per-run budget and a 24-hour cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ...config import Settings
from ...models import SearchCache, utcnow
from .base import (
    BudgetedSearchProvider,
    SearchBudget,
    SearchProvider,
    SearchProviderError,
    SearchResult,
    query_hash,
)
from .duckduckgo import DuckDuckGoProvider
from .serper import SerperProvider


class AutoSearchProvider(SearchProvider):
    """Prefer Serper, fall back to DuckDuckGo on error or zero results."""

    name = "auto"

    def __init__(self, primary: SearchProvider, fallback: SearchProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        errors: list[str] = []
        for provider in (self.primary, self.fallback):
            try:
                results = provider.search(query, limit=limit, recency_days=recency_days)
            except SearchProviderError as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            if results:
                return results
        if errors:
            raise SearchProviderError("; ".join(errors), provider=self.name)
        return []

    def health(self) -> bool:
        return self.primary.health() or self.fallback.health()


class CachedSearchProvider(SearchProvider):
    def __init__(
        self,
        inner: SearchProvider,
        session_factory,
        *,
        ttl_hours: int = 24,
        clock=utcnow,
    ) -> None:
        self.inner = inner
        self.name = inner.name
        self.ttl_hours = ttl_hours
        self._session_factory = session_factory
        self._clock = clock

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        digest = query_hash(query, limit, recency_days)
        now = self._clock()

        with self._session_factory() as session:
            row = session.scalar(
                select(SearchCache).where(
                    SearchCache.provider == self.inner.name,
                    SearchCache.query_hash == digest,
                )
            )
            if row and row.expires_at > now:
                return [SearchResult.from_dict(item) for item in row.results_json]

        results = self.inner.search(query, limit=limit, recency_days=recency_days)
        expires_at = _plus_hours(now, self.ttl_hours)
        payload = [result.as_dict() for result in results]

        with self._session_factory() as session:
            row = session.scalar(
                select(SearchCache).where(
                    SearchCache.provider == self.inner.name,
                    SearchCache.query_hash == digest,
                )
            )
            if row is None:
                session.add(
                    SearchCache(
                        provider=self.inner.name,
                        query_hash=digest,
                        query=query[:500],
                        results_json=payload,
                        expires_at=expires_at,
                    )
                )
            else:
                row.results_json = payload
                row.query = query[:500]
                row.expires_at = expires_at
            session.commit()
        return results

    def health(self) -> bool:
        return self.inner.health()


def _plus_hours(now: str, hours: int) -> str:
    moment = datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(hours=hours)
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_search_provider(
    settings: Settings,
    *,
    session_factory=None,
    client=None,
    budget: SearchBudget | None = None,
) -> SearchProvider:
    duck = DuckDuckGoProvider(timeout_s=settings.search_timeout_s, client=client)

    if settings.search_provider == "duckduckgo":
        provider: SearchProvider = duck
    elif settings.search_provider == "serper":
        provider = SerperProvider(
            settings.serper_api_key,
            timeout_s=settings.search_timeout_s,
            client=client,
        )
    else:  # auto
        if settings.serper_api_key:
            serper = SerperProvider(
                settings.serper_api_key,
                timeout_s=settings.search_timeout_s,
                client=client,
            )
            provider = AutoSearchProvider(serper, duck)
        else:
            provider = duck

    if budget is not None:
        provider = BudgetedSearchProvider(provider, budget)

    if session_factory is not None and settings.search_cache_ttl_hours > 0:
        provider = CachedSearchProvider(
            provider,
            session_factory,
            ttl_hours=settings.search_cache_ttl_hours,
        )
    return provider
