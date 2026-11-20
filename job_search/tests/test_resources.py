"""Resources dashboard: call ledger, search ledger, per-job usage and charts."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db import get_session_factory
from app.models import Job, LlmCall, SearchCall
from app.providers.call_context import call_context
from app.providers.llm.base import ChatMessage, LLMResponse
from app.providers.llm.ledger import LedgerLLMProvider
from app.providers.search.base import SearchProvider, SearchResult
from app.providers.search.ledger import LedgerSearchProvider
from app.providers.search.pricing import estimate_search_cost
from app.usage import UsageFilters, build_report, parse_filters
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _run(client) -> int:
    login(client)
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


# ---------------------------------------------------------------- pages


def test_resources_requires_a_session(client):
    response = client.get("/resources", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_resources_page_shows_job_totals_from_the_ledger(client, settings):
    job_id = _run(client)
    factory = get_session_factory(settings)

    with factory() as db:
        calls = db.scalars(select(LlmCall).where(LlmCall.job_id == job_id)).all()
        assert len(calls) == 14  # every pipeline step makes one call
        assert {call.skill for call in calls} >= {"job_extraction", "cv_writing"}
        assert all(call.job_id == job_id for call in calls)
        tokens = sum(call.tokens_in + call.tokens_out for call in calls)
        assert tokens > 0

    html = client.get("/resources").text
    assert "Resources" in html
    assert "Senior Machine Learning Engineer" in html
    assert "13" in html  # LLM calls card
    assert "Estimated spend" in html


def test_resources_filters_apply(client):
    _run(client)
    assert "No usage matches these filters" in client.get("/resources?q=no-such-job").text
    page = client.get("/resources?days=7&status=ready").text
    assert "Senior Machine Learning Engineer" in page
    assert client.get("/resources?days=9999").status_code == 200
    assert "No usage matches these filters" in client.get("/resources?status=withdrawn").text


def test_resources_model_filter_keeps_pages_working(client):
    _run(client)
    html = client.get("/resources?model=fake-small").text
    assert "Senior Machine Learning Engineer" in html
    assert "Web searches" in html


def test_job_detail_lists_its_llm_calls(client):
    job_id = _run(client)
    html = client.get(f"/jobs/{job_id}").text
    assert "LLM calls" in html
    assert "Reading the posting" in html  # a skill label from the ledger table
    assert "fake-large" in html


def test_company_page_shows_usage_and_404s_for_missing(client, settings):
    job_id = _run(client)
    factory = get_session_factory(settings)
    with factory() as db:
        company_id = db.get(Job, job_id).company_id

    html = client.get(f"/companies/{company_id}").text
    assert "Acme Speech" in html
    assert "Senior Machine Learning Engineer" in html
    assert "Estimated spend" in html
    assert client.get("/companies/999999").status_code == 404


# ---------------------------------------------------------------- llm ledger


class StubLLM:
    name = "stub"
    models = {"large": "stub-large", "small": "stub-small"}

    def __init__(self) -> None:
        self.hits = 0

    def complete(self, messages, **kwargs):
        self.hits += 1
        return LLMResponse(
            text='{"ok": true}',
            model=kwargs.get("model") or "stub-large",
            tokens_in=100,
            tokens_out=20,
            latency_ms=7,
        )

    def model_for(self, tier: str) -> str:
        return self.models[tier]

    def health(self) -> bool:
        return True


def test_llm_ledger_records_calls_inside_a_call_context(client, settings):
    job_id = _run(client)
    inner = StubLLM()
    ledger = LedgerLLMProvider(inner, get_session_factory(settings))
    message = ChatMessage("user", "skill: cv_writing")

    with call_context(job_id=job_id, run_id=1, skill="cv_writing"):
        response = ledger.complete([message], model="stub-large")

    assert response.tokens_in == 100
    with get_session_factory(settings)() as db:
        row = db.scalar(
            select(LlmCall)
            .where(LlmCall.job_id == job_id, LlmCall.skill == "cv_writing")
            .order_by(LlmCall.id.desc())
            .limit(1)
        )
        assert row is not None
        assert row.model == "stub-large"
        assert row.tokens_in == 100
        assert row.cost_usd == 0.0  # unpriced model is never guessed
    # The pipeline run already recorded eleven calls; this test adds one more.


def test_llm_ledger_skips_calls_without_a_context(client, settings):
    ledger = LedgerLLMProvider(StubLLM(), get_session_factory(settings))
    ledger.complete([ChatMessage("user", "unattributed")])
    with get_session_factory(settings)() as db:
        assert db.scalar(select(func.count(LlmCall.id))) == 0


# ---------------------------------------------------------------- search ledger


class StubSearch(SearchProvider):
    name = "serper"

    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results

    def search(self, query, *, limit=5, recency_days=None):
        return self.results

    def health(self) -> bool:
        return True


def _result(provider: str = "serper", cached: bool = False) -> SearchResult:
    return SearchResult(
        title="Acme careers",
        url="https://acme.example/careers",
        snippet="Open roles",
        provider=provider,
        cached=cached,
    )


def test_search_ledger_ignores_searches_outside_a_run(client, settings):
    ledger = LedgerSearchProvider(StubSearch([_result()]), get_session_factory(settings))

    results = ledger.search("acme speech news", limit=5)

    assert len(results) == 1
    with get_session_factory(settings)() as db:
        assert db.scalar(select(func.count(SearchCall.id))) == 0


def test_search_ledger_records_calls_and_costs(client, settings):
    factory = get_session_factory(settings)
    job_id = _run(client)
    ledger = LedgerSearchProvider(StubSearch([_result("serper")]), factory)

    with call_context(job_id=job_id, run_id=1, skill="company_research"):
        ledger.search("acme speech news", limit=5)

    with factory() as db:
        row = db.scalar(select(SearchCall).where(SearchCall.job_id == job_id))
        assert row is not None
        assert row.provider == "serper"
        assert row.cost_usd == estimate_search_cost("serper")
        assert row.cached is False
        assert row.results == 1

        report = build_report(db, UsageFilters(days=0))
        assert report.totals.search_calls == 1
        assert report.totals.search_cost_usd > 0
        assert report.totals.total_cost == round(
            report.totals.cost_usd + report.totals.search_cost_usd, 6
        )


def test_search_ledger_records_cache_hits_as_free(client, settings):
    factory = get_session_factory(settings)
    job_id = _run(client)
    ledger = LedgerSearchProvider(StubSearch([_result("serper", cached=True)]), factory)

    with call_context(job_id=job_id, run_id=1, skill="company_research"):
        ledger.search("cached query", limit=5)

    with factory() as db:
        row = db.scalar(select(SearchCall).where(SearchCall.job_id == job_id))
        assert row.cached is True
        assert row.cost_usd == 0.0


# ---------------------------------------------------------------- aggregation


def test_parse_filters_clamps_window_and_status(client):
    filters = parse_filters({"days": "9999", "status": "bogus", "q": "  acme  "})
    assert filters.days == 30
    assert filters.status == ""
    assert filters.query == "acme"

def test_interview_pack_renders_as_scannable_blocks(client):
    job_id = _run(client)
    html = client.get(f"/jobs/{job_id}").text
    pack = html.split('id="interview-panel"')[1].split("</section>")[0]

    assert "prose--spoken" in pack
    assert "prose-h--delivery" in pack
    assert "interview-doc__title" in pack
    assert pack.count("<p>") >= 6  # short paragraphs, not one wall of text
