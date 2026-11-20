"""Search composition: Serper/Exa/DuckDuckGo auto fallback, budget and cache."""

from __future__ import annotations

from dataclasses import replace
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
from .exa import ExaProvider
from .ledger import LedgerSearchProvider
from .serper import SerperProvider


class AutoSearchProvider(SearchProvider):
    """Try keyed providers in order, then DuckDuckGo, on error or zero results."""

    name = "auto"

    def __init__(
        self,
        primary: SearchProvider,
        fallback: SearchProvider | None = None,
        *,
        extra: tuple[SearchProvider, ...] = (),
    ) -> None:
        self.providers = (primary, *( (fallback,) if fallback is not None else ()), *extra)
        self.primary = primary
        self.fallback = fallback or primary

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        errors: list[str] = []
        for provider in self.providers:
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
        return any(provider.health() for provider in self.providers)


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
                return [
                    replace(SearchResult.from_dict(item), cached=True)
                    for item in row.results_json
                ]

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
    elif settings.search_provider == "exa":
        provider = ExaProvider(
            settings.exa_api_key,
            timeout_s=settings.search_timeout_s,
            client=client,
        )
    else:  # auto
        chain: list[SearchProvider] = []
        if settings.serper_api_key:
            chain.append(
                SerperProvider(
                    settings.serper_api_key,
                    timeout_s=settings.search_timeout_s,
                    client=client,
                )
            )
        if settings.exa_api_key:
            chain.append(
                ExaProvider(
                    settings.exa_api_key,
                    timeout_s=settings.search_timeout_s,
                    client=client,
                )
            )
        chain.append(duck)
        provider = (
            chain[0]
            if len(chain) == 1
            else AutoSearchProvider(chain[0], chain[1], extra=tuple(chain[2:]))
        )

    if budget is not None:
        provider = BudgetedSearchProvider(provider, budget)

    if session_factory is not None and settings.search_cache_ttl_hours > 0:
        provider = CachedSearchProvider(
            provider,
            session_factory,
            ttl_hours=settings.search_cache_ttl_hours,
        )

    if session_factory is not None:
        # Outside the cache, so cache hits are recorded as free searches.
        provider = LedgerSearchProvider(provider, session_factory)
    return provider
