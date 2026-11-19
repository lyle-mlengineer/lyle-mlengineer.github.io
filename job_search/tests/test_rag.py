from __future__ import annotations

import re

import pytest
from sqlalchemy import func, select

from app.db import get_session_factory
from app.models import PortfolioChunk, PortfolioDoc
from app.rag.grounding import check_numbers, extract_numbers, is_grounded
from app.rag.ingest import MAX_CHARS, chunk_markdown, sync_portfolio
from app.rag.retrieve import build_query, query_terms, retrieve, retrieve_for_job
from tests.conftest import login

EXPERIENCE = """
# Lyle Okoth — experience

## Machine Learning Engineer — SautiFlow Labs, Nairobi (2024 – present)

- Cut Swahili and Sheng ASR word error rate from 23.4% to 11.8% by LoRA fine-tuning Whisper-large-v3 on 1,240 hours of in-house audio.
- Shipped streaming speech-to-speech translation at **310 ms median / 780 ms p95 first-audio latency** across six language pairs.
- Compressed a 1.6 GB TTS checkpoint to **480 MB** with int8 quantisation and KV caching: **42 concurrent voices per GPU**.
"""


def test_chunking_keeps_headings_and_metric_sentences():
    chunks = chunk_markdown(EXPERIENCE)
    assert chunks
    assert all(chunk.heading.startswith("Machine Learning Engineer") for chunk in chunks)
    joined = "\n".join(chunk.text for chunk in chunks)
    assert "23.4% to 11.8%" in joined
    assert all(len(chunk.text) <= MAX_CHARS + 200 for chunk in chunks)


def test_chunking_splits_a_long_document_at_word_boundaries():
    body = "## Section\n\n" + ("word " * 1500)
    chunks = chunk_markdown(f"# Doc\n\n{body}")
    assert len(chunks) > 1
    assert all(len(chunk.text) <= MAX_CHARS + 200 for chunk in chunks)
    assert all(not chunk.text.startswith("ord ") for chunk in chunks)


def test_second_ingest_writes_nothing(authed, settings):
    assert authed.get("/").status_code == 200  # startup already indexed the corpus
    factory = get_session_factory(settings)
    with factory() as session:
        report = sync_portfolio(session, settings)
        assert report.docs_indexed == 0
        assert report.docs_removed == 0
        assert report.chunks_written == 0
        assert report.docs_skipped >= 5


def test_index_has_docs_and_chunks(authed, settings):
    factory = get_session_factory(settings)
    with factory() as session:
        assert session.scalar(select(func.count(PortfolioDoc.id))) >= 5
        assert session.scalar(select(func.count(PortfolioChunk.id))) >= 20


def test_targeted_query_surfaces_the_wer_metric(authed, settings):
    factory = get_session_factory(settings)
    with factory() as session:
        results = retrieve(
            session,
            build_query(
                {
                    "title": "Speech Recognition Engineer",
                    "skills": ["ASR", "Whisper", "Swahili", "WER"],
                }
            ),
            limit=6,
        )
    assert results
    combined = "\n".join(chunk.text for chunk in results)
    assert "23.4%" in combined
    assert "11.8%" in combined
    assert all(chunk.citation for chunk in results)


def test_retrieval_respects_the_character_budget(authed, settings):
    factory = get_session_factory(settings)
    with factory() as session:
        results = retrieve_for_job(
            session,
            {"title": "Machine Learning Engineer", "skills": ["speech", "PyTorch", "deployment"]},
            limit=8,
            max_chars=900,
        )
    assert sum(len(chunk.text) for chunk in results) <= max(900, len(results[0].text))


def test_empty_query_returns_nothing(authed, settings):
    factory = get_session_factory(settings)
    with factory() as session:
        assert retrieve(session, "") == []


def test_query_terms_are_deduplicated_and_stopworded():
    terms = query_terms("Machine learning engineer with experience in machine learning and speech")
    assert terms.count("machine") == 1
    assert "with" not in terms
    assert "experience" not in terms


def test_numbers_extract_units_and_commas():
    claims = extract_numbers("23.4% to 11.8%, 1,240 hours, 310 ms, 42 voices, 480 MB")
    assert [claim.value for claim in claims][:3] == ["23.4", "11.8", "1240"]
    assert claims[2].unit == "hours"
    assert claims[3].unit == "ms"


def test_grounding_accepts_corpus_metrics_and_flags_invented_ones():
    assert is_grounded("Cut WER from 23.4% to 11.8% on 1,240 hours, at 310 ms.", EXPERIENCE)
    assert check_numbers("Grew retention by 35% and served 999 ms latency.", EXPERIENCE) == ["35%", "999 ms"]


def test_grounding_report_lists_checked_tokens():
    from app.rag.grounding import grounding_report

    report = grounding_report("Served 42 voices and 75 users.", EXPERIENCE)
    assert any(token.startswith("42") for token in report["checked"])
    assert report["unsupported"] == ["75 users"]


def test_settings_page_shows_index_and_can_reindex(authed):
    page = authed.get("/settings")
    assert page.status_code == 200
    assert "Portfolio index" in page.text
    assert re.search(r"\d+ docs · \d+ chunks", page.text)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)

    response = authed.post(
        "/settings/reindex",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 303
    follow = authed.get(response.headers["location"])
    assert "Portfolio index rebuilt" in follow.text


def test_reindex_requires_csrf(authed):
    response = authed.post("/settings/reindex", data={"csrf_token": "wrong"}, follow_redirects=False)
    assert response.status_code == 403


def test_reindex_requires_login(client):
    response = client.post("/settings/reindex", data={}, follow_redirects=False)
    assert response.status_code in (303, 401)


@pytest.fixture()
def authed(client):
    login(client)
    return client


def test_reindex_api_returns_a_report(authed):
    page = authed.get("/settings")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = authed.post("/api/portfolio/reindex", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is False
    assert body["docs_skipped"] >= 5
    assert body["chunks"] == 0


def test_reindex_api_requires_csrf(authed):
    assert authed.post("/api/portfolio/reindex").status_code == 403
