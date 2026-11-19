"""Serper.dev search (Google results).

Serper is the primary backend because careers pages and "company + news" queries
are exactly where Google's index beats DuckDuckGo.
"""

from __future__ import annotations

import httpx

from .base import SearchProvider, SearchProviderError, SearchResult

SERPER_ENDPOINT = "https://google.serper.dev/search"


def _recency_window(days: int | None) -> str | None:
    if not days or days <= 0:
        return None
    if days <= 1:
        return "qdr:d"
    if days <= 7:
        return "qdr:w"
    if days <= 31:
        return "qdr:m"
    return "qdr:y"


class SerperProvider(SearchProvider):
    name = "serper"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_s: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise SearchProviderError("SKIPPER_SERPER_API_KEY is required for serper search.", provider=self.name)
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_s)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        payload: dict[str, object] = {"q": query, "num": max(1, min(limit, 10))}
        window = _recency_window(recency_days)
        if window:
            payload["tbs"] = window

        try:
            response = self._client.post(
                SERPER_ENDPOINT,
                json=payload,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "Skipper/0.1",
                },
                timeout=self.timeout_s,
            )
        except httpx.HTTPError as exc:
            raise SearchProviderError(f"Serper request failed: {exc}", provider=self.name) from exc

        if response.status_code >= 400:
            raise SearchProviderError(
                f"Serper returned HTTP {response.status_code}: {response.text[:200]}",
                provider=self.name,
                status=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SearchProviderError("Serper returned non-JSON.", provider=self.name) from exc

        results: list[SearchResult] = []
        for rank, item in enumerate(data.get("organic") or [], start=1):
            link = (item.get("link") or "").strip()
            if not link:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or link).strip(),
                    url=link,
                    snippet=(item.get("snippet") or "").strip(),
                    provider=self.name,
                    rank=rank,
                )
            )
            if len(results) >= limit:
                break
        return results

    def health(self) -> bool:
        try:
            response = self._client.get(
                "https://google.serper.dev/",
                headers={"X-API-KEY": self.api_key},
                timeout=5.0,
            )
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
