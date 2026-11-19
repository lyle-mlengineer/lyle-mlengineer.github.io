"""Per-search ledger.

Serper charges per query, so a job's real cost is its model calls plus its
searches. This wrapper sits outside the cache: a cached search is recorded too,
marked ``cached`` and priced at zero, which keeps "how much research did this job
need" separate from "what did it cost".

Failed searches are not recorded — providers do not bill for an error response —
and a ledger write never fails the search that already happened.
"""

from __future__ import annotations

import logging
import time

from ...models import SearchCall
from ..call_context import current_call_context
from .base import SearchProvider, SearchResult
from .pricing import estimate_search_cost

logger = logging.getLogger("skipper.search")


class LedgerSearchProvider(SearchProvider):
    def __init__(self, inner: SearchProvider, session_factory) -> None:
        self.inner = inner
        self.name = inner.name
        self._session_factory = session_factory

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        started = time.monotonic()
        results = self.inner.search(query, limit=limit, recency_days=recency_days)
        duration_ms = int((time.monotonic() - started) * 1000)
        self.record(query, results, duration_ms)
        return results

    def record(self, query: str, results: list[SearchResult], duration_ms: int) -> None:
        context = current_call_context()
        if context is None:  # discovery and ad-hoc searches have no job yet
            return
        cached = bool(results) and all(result.cached for result in results)
        provider = results[0].provider if results else self.inner.name
        row = SearchCall(
            job_id=context.job_id,
            run_id=context.run_id,
            skill=context.skill,
            provider=provider or self.inner.name,
            query=query[:500],
            results=len(results),
            cost_usd=estimate_search_cost(provider, cached=cached),
            cached=cached,
            duration_ms=duration_ms,
        )
        try:
            with self._session_factory() as session:
                session.add(row)
                session.commit()
        except Exception:  # pragma: no cover - the run matters more than the ledger
            logger.warning("could not record a web search", exc_info=True)

    def health(self) -> bool:
        return self.inner.health()
