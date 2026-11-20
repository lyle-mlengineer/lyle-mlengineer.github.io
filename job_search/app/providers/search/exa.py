"""Exa semantic web search.

Exa returns ranked documents rather than Google's ten blue links, which suits
company research: a query like "Acme Voice product pricing" finds pages that
talk about the product even when the words differ. The result snippet comes
from Exa's extracted page text unless the response already includes highlights.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from .base import SearchProvider, SearchProviderError, SearchResult

EXA_ENDPOINT = "https://api.exa.ai/search"
EXA_MAX_TEXT_CHARS = 700


def _start_published(recency_days: int | None) -> str | None:
    if not recency_days or recency_days <= 0:
        return None
    moment = datetime.now(UTC) - timedelta(days=recency_days)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ExaProvider(SearchProvider):
    name = "exa"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_s: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise SearchProviderError("SKIPPER_EXA_API_KEY is required for exa search.", provider=self.name)
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
        payload: dict[str, object] = {
            "query": query,
            "type": "auto",
            "numResults": max(1, min(limit, 20)),
            "contents": {"text": {"maxCharacters": EXA_MAX_TEXT_CHARS}},
        }
        start = _start_published(recency_days)
        if start:
            payload["startPublishedDate"] = start

        try:
            response = self._client.post(
                EXA_ENDPOINT,
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "Skipper/0.1",
                },
                timeout=self.timeout_s,
            )
        except httpx.HTTPError as exc:
            raise SearchProviderError(f"Exa request failed: {exc}", provider=self.name) from exc

        if response.status_code >= 400:
            raise SearchProviderError(
                f"Exa returned HTTP {response.status_code}: {response.text[:200]}",
                provider=self.name,
                status=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SearchProviderError("Exa returned non-JSON.", provider=self.name) from exc

        results: list[SearchResult] = []
        for rank, item in enumerate(data.get("results") or [], start=1):
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            snippet = str(item.get("text") or "").strip()
            highlights = item.get("highlights")
            if isinstance(highlights, list) and highlights:
                snippet = " ".join(str(value).strip() for value in highlights if value)
            results.append(
                SearchResult(
                    title=(str(item.get("title") or "").strip() or url),
                    url=url,
                    snippet=" ".join(snippet.split())[:600],
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
                "https://api.exa.ai/",
                headers={"x-api-key": self.api_key},
                timeout=5.0,
            )
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
