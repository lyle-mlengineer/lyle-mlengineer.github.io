"""DuckDuckGo HTML search — the no-key fallback.

The HTML endpoint is unversioned and can change, so parsing is deliberately
forgiving and a lite-endpoint retry covers layout changes. If both fail the
company-research step degrades to "no external sources" rather than inventing
facts.
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import SearchProvider, SearchProviderError, SearchResult

HTML_ENDPOINT = "https://html.duckduckgo.com/html/"
LITE_ENDPOINT = "https://lite.duckduckgo.com/lite/"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def unwrap_redirect(href: str) -> str:
    """DuckDuckGo wraps links as /l/?uddg=<encoded>; return the real target."""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return href


def parse_results(html: str, *, limit: int = 5) -> list[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchResult] = []

    for block in soup.select("div.result, div.web-result"):
        anchor = block.select_one("a.result__a, a.result-link")
        if not anchor:
            continue
        url = unwrap_redirect(anchor.get("href", ""))
        if not url.startswith(("http://", "https://")):
            continue
        snippet_node = block.select_one(".result__snippet, .result-snippet")
        results.append(
            SearchResult(
                title=anchor.get_text(" ", strip=True),
                url=url,
                snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
                provider="duckduckgo",
                rank=len(results) + 1,
            )
        )
        if len(results) >= limit:
            return results

    if results:
        return results

    # Lite layout: table rows with a link and a snippet cell, no wrappers.
    for anchor in soup.select("a.result-link"):
        url = unwrap_redirect(anchor.get("href", ""))
        if not url.startswith(("http://", "https://")):
            continue
        row = anchor.find_parent("tr")
        snippet_node = row.select_one(".result-snippet") if row else None
        if snippet_node is None and row is not None:
            next_row = row.find_next_sibling("tr")
            snippet_node = next_row.select_one(".result-snippet") if next_row else None
        results.append(
            SearchResult(
                title=anchor.get_text(" ", strip=True),
                url=url,
                snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
                provider="duckduckgo",
                rank=len(results) + 1,
            )
        )
        if len(results) >= limit:
            break
    return results


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def __init__(
        self,
        *,
        timeout_s: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout_s = timeout_s
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"},
            follow_redirects=True,
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        recency_days: int | None = None,
    ) -> list[SearchResult]:
        params: dict[str, str] = {"q": query}
        if recency_days:
            params["df"] = "d" if recency_days <= 1 else "w" if recency_days <= 7 else "m"

        for endpoint in (HTML_ENDPOINT, LITE_ENDPOINT):
            try:
                response = self._client.get(endpoint, params=params, timeout=self.timeout_s)
            except httpx.HTTPError as exc:
                raise SearchProviderError(
                    f"DuckDuckGo request failed: {exc}", provider=self.name
                ) from exc
            if response.status_code >= 400:
                raise SearchProviderError(
                    f"DuckDuckGo returned HTTP {response.status_code}",
                    provider=self.name,
                    status=response.status_code,
                )
            results = parse_results(response.text, limit=limit)
            if results:
                return results
        return []

    def health(self) -> bool:
        try:
            response = self._client.get(HTML_ENDPOINT, params={"q": "test"}, timeout=5.0)
            return response.status_code < 400
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
