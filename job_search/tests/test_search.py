from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.db import get_session_factory
from app.providers.search.base import (
    BudgetedSearchProvider,
    BudgetExceeded,
    SearchBudget,
    SearchProvider,
    SearchProviderError,
    SearchResult,
)
from app.providers.search.duckduckgo import DuckDuckGoProvider, parse_results, unwrap_redirect
from app.providers.search.ledger import LedgerSearchProvider
from app.providers.search.registry import (
    AutoSearchProvider,
    CachedSearchProvider,
    build_search_provider,
)
from app.providers.search.serper import SerperProvider

DDG_HTML = """
<html><body>
<div class="result results_links">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facme.example%2Fcareers&amp;rut=abc">Acme careers</a>
  <a class="result__snippet">Open roles at Acme Voice.</a>
</div>
<div class="result results_links">
  <a class="result__a" href="https://news.example/acme-funding">Acme raises a round</a>
  <div class="result__snippet">The company announced new funding.</div>
</div>
</body></html>
"""

DDG_LITE = """
<html><body><table>
<tr><td><a class="result-link" href="https://acme.example/jobs/1">Senior ML Engineer</a></td></tr>
<tr><td class="result-snippet">Speech recognition role in Nairobi.</td></tr>
</table></body></html>
"""


# ---------------------------------------------------------------- parsing


def test_unwrap_duckduckgo_redirects():
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Facme.example%2Fcareers&rut=x"
    assert unwrap_redirect(href) == "https://acme.example/careers"
    assert unwrap_redirect("https://acme.example/direct") == "https://acme.example/direct"


def test_parse_ddg_results_extracts_titles_links_and_snippets():
    results = parse_results(DDG_HTML, limit=5)
    assert [result.url for result in results] == [
        "https://acme.example/careers",
        "https://news.example/acme-funding",
    ]
    assert results[0].title == "Acme careers"
    assert results[0].snippet == "Open roles at Acme Voice."
    assert results[0].provider == "duckduckgo"
    assert [result.rank for result in results] == [1, 2]


def test_parse_ddg_results_honours_the_limit():
    assert len(parse_results(DDG_HTML, limit=1)) == 1


def test_parse_ddg_lite_layout():
    results = parse_results(DDG_LITE, limit=5)
    assert len(results) == 1
    assert results[0].url == "https://acme.example/jobs/1"
    assert "Nairobi" in results[0].snippet


# ---------------------------------------------------------------- serper


def test_serper_maps_organic_results():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "organic": [
                    {"title": "Acme careers", "link": "https://acme.example/careers", "snippet": "Join us"},
                    {"title": "Acme news", "link": "https://news.example/acme", "snippet": "Funding"},
                ]
            },
        )

    provider = SerperProvider("serper-key", client=httpx.Client(transport=httpx.MockTransport(handler)))
    results = provider.search("Acme Voice careers", limit=2, recency_days=7)

    payload = json.loads(seen[0].content)
    assert payload == {"q": "Acme Voice careers", "num": 2, "tbs": "qdr:w"}
    assert seen[0].headers["x-api-key"] == "serper-key"
    assert results[0].provider == "serper"
    assert results[1].rank == 2


def test_serper_raises_on_http_errors():
    provider = SerperProvider(
        "serper-key",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403, text="no"))),
    )
    with pytest.raises(SearchProviderError) as excinfo:
        provider.search("anything")
    assert excinfo.value.status == 403


def test_serper_requires_a_key():
    with pytest.raises(SearchProviderError):
        SerperProvider("")


# ---------------------------------------------------------------- duckduckgo


def test_duckduckgo_falls_back_to_the_lite_endpoint():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        body = DDG_HTML if "html.duckduckgo.com" in str(request.url) else DDG_LITE
        if "html.duckduckgo.com" in str(request.url):
            body = "<html><body>No results</body></html>"
        return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})

    provider = DuckDuckGoProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    results = provider.search("acme", limit=5)

    assert paths == ["/html/", "/lite/"]
    assert results[0].title == "Senior ML Engineer"


# ---------------------------------------------------------------- auto + budget


class StubSearch(SearchProvider):
    def __init__(self, name: str, results: list[SearchResult] | None = None, error: bool = False):
        self.name = name
        self.results = results or []
        self.error = error
        self.calls = 0

    def search(self, query, *, limit=5, recency_days=None):
        self.calls += 1
        if self.error:
            raise SearchProviderError("boom", provider=self.name)
        return self.results

    def health(self):
        return True


def _result(url: str = "https://acme.example") -> SearchResult:
    return SearchResult(title="Acme", url=url, snippet="s", provider="stub", rank=1)


def test_auto_provider_falls_back_when_primary_fails():
    primary = StubSearch("serper", error=True)
    fallback = StubSearch("duckduckgo", results=[_result()])

    results = AutoSearchProvider(primary, fallback).search("acme")

    assert results[0].url == "https://acme.example"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_auto_provider_falls_back_when_primary_is_empty():
    primary = StubSearch("serper", results=[])
    fallback = StubSearch("duckduckgo", results=[_result()])
    assert AutoSearchProvider(primary, fallback).search("acme")[0].provider == "stub"


def test_budget_stops_after_the_limit():
    provider = BudgetedSearchProvider(StubSearch("stub", results=[_result()]), SearchBudget(1))
    provider.search("one")
    with pytest.raises(BudgetExceeded):
        provider.search("two")


# ---------------------------------------------------------------- cache + registry


def test_search_cache_skips_the_second_call(client, settings):
    inner = StubSearch("stub", results=[_result()])
    cached = CachedSearchProvider(inner, get_session_factory(settings))

    first = cached.search("acme careers", limit=3)
    second = cached.search("acme careers", limit=3)

    assert inner.calls == 1
    assert [result.url for result in second] == [result.url for result in first]


def test_search_cache_expires(client, settings):
    inner = StubSearch("stub", results=[_result()])
    now = [datetime.now(UTC)]

    def clock() -> str:
        return now[0].replace(microsecond=0).isoformat().replace("+00:00", "Z")

    cached = CachedSearchProvider(inner, get_session_factory(settings), ttl_hours=24, clock=clock)

    cached.search("acme", limit=3)
    now[0] += timedelta(hours=25)
    cached.search("acme", limit=3)

    assert inner.calls == 2


def test_cache_hits_do_not_consume_the_budget(client, settings):
    budget = SearchBudget(1)
    inner = BudgetedSearchProvider(StubSearch("stub", results=[_result()]), budget)
    cached = CachedSearchProvider(inner, get_session_factory(settings))

    cached.search("acme", limit=3)
    cached.search("acme", limit=3)

    assert budget.used == 1
    with pytest.raises(BudgetExceeded):
        cached.search("different query", limit=3)


def test_registry_defaults_to_duckduckgo_without_a_serper_key(client, settings):
    provider = build_search_provider(settings, session_factory=get_session_factory(settings))
    # The ledger is the outermost wrapper so every search, cached or not, is recorded.
    assert isinstance(provider, LedgerSearchProvider)
    assert isinstance(provider.inner, CachedSearchProvider)
    assert provider.name == "duckduckgo"
