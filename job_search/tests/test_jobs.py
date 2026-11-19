from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db import get_session_factory
from app.jobs.render import markdown_to_html
from app.models import Artifact, Company, Job, Run
from app.providers.fetch.extract import ExtractedPage
from app.providers.fetch.http import FetchResult
from app.providers.llm.fake import FakeLLMProvider
from app.skills.registry import FAKE_RESPONSES
from app.utils import canonicalize_url, fingerprint
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""

URL_TEXT = """\
Staff Data Engineer at Northwind Labs.
Northwind is hiring a staff data engineer to own the streaming platform behind its logistics products.
You will design Kafka pipelines, model warehouse tables and mentor three engineers.
The role is hybrid in Nairobi and requires Python, SQL and dbt.
"""


class StubFetcher:
    def __init__(self, text: str = URL_TEXT, *, ok: bool = True, title: str = "Staff Data Engineer") -> None:
        self.text = text
        self.ok = ok
        self.title = title
        self.urls: list[str] = []

    def close(self) -> None:
        pass

    def fetch(self, url: str) -> FetchResult:
        self.urls.append(url)
        page = ExtractedPage(
            url=url,
            title=self.title,
            text=self.text,
            description_md="A data engineering role.",
            char_count=len(self.text),
            ok=self.ok,
            reason="" if self.ok else "too little text",
        )
        return FetchResult(
            url=url,
            final_url=url,
            status=200,
            content_type="text/html",
            page=page,
            html="<html></html>",
        )


@pytest.fixture()
def authed(client):
    login(client)
    return client


def headers(client) -> dict[str, str]:
    csrf = client.get("/api/auth/me").json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


def add(client, payload: dict) -> object:
    return client.post("/api/jobs", json=payload, headers=headers(client))


def test_text_ingestion_runs_extraction_and_summary(authed, settings):
    response = add(authed, {"source_text": TEXT})
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["job_url"] == f"/jobs/{body['job_id']}"

    run = authed.get(body["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert run["progress_pct"] == 100
    assert [step["skill"] for step in run["steps"]] == [
        "job_extraction",
        "job_summary",
        "company_research",
        "cv_writing",
        "cover_letter",
        "email_writing",
        "tell_me_about_yourself",
        "work_history",
        "proud_project",
        "technical_interview",
        "behavioral_interview",
    ]
    assert all(step["status"] == "succeeded" for step in run["steps"])

    detail = authed.get(body["job_url"])
    assert detail.status_code == 200
    assert "Senior Machine Learning Engineer" in detail.text
    assert "Acme Speech" in detail.text
    assert "What the posting asks for" in detail.text
    assert "Ready" in detail.text

    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, body["job_id"])
        assert job.status == "ready"
        assert job.extract_json["company_name"] == "Acme Speech"
        assert job.company.name == "Acme Speech"
        assert job.summary_md.startswith("# Senior Machine Learning Engineer at Acme Speech")
        assert db.scalar(select(func.count(Company.id))) == 1
        artifacts = db.scalars(select(Artifact).where(Artifact.job_id == job.id)).all()
        kinds = {artifact.kind for artifact in artifacts if artifact.is_current}
        assert {
            "job_summary", "cv_pdf", "cv_docx", "cover_letter_pdf",
            "cover_letter_docx", "email", "technical_interview",
        } <= kinds


def test_duplicate_text_returns_409_and_attach_starts_another_run(authed):
    first = add(authed, {"source_text": TEXT})
    assert first.status_code == 202
    job_id = first.json()["job_id"]

    duplicate = add(authed, {"source_text": TEXT})
    assert duplicate.status_code == 409
    error = duplicate.json()["error"]
    assert error["code"] == "duplicate_job"
    assert error["details"]["job_id"] == job_id

    attached = authed.post(
        "/api/jobs?attach=1",
        json={"source_text": TEXT},
        headers=headers(authed),
    )
    assert attached.status_code == 202
    assert attached.json()["attached"] is True
    assert attached.json()["job_id"] == job_id


def test_short_text_is_rejected_with_a_helpful_message(authed):
    response = add(authed, {"source_text": "too short"})
    assert response.status_code == 422
    assert "too short" in response.json()["error"]["message"]
    assert authed.get("/jobs").status_code == 200  # no job row


def test_link_and_text_together_are_rejected(authed):
    response = add(authed, {"source_text": TEXT, "source_url": "https://example.com/job"})
    assert response.status_code == 422


def test_create_requires_login_and_csrf(client):
    assert client.post("/api/jobs", json={"source_text": TEXT}).status_code == 401
    login(client)
    assert client.post("/api/jobs", json={"source_text": TEXT}).status_code == 403


def test_url_ingestion_uses_canonical_url_and_keeps_a_source(authed, settings):
    stub = StubFetcher()
    authed.app.state.fetcher = stub
    response = add(
        authed,
        {"source_url": "HTTPS://Example.COM/jobs/42?utm_source=x&team=data#apply"},
    )
    assert response.status_code == 202, response.text
    assert stub.urls == ["https://example.com/jobs/42?team=data"]

    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, response.json()["job_id"])
        assert job.source_type == "website"
        assert job.canonical_url == "https://example.com/jobs/42?team=data"
        assert job.sources[0].kind == "posting"


def test_unreadable_page_asks_for_pasted_text(authed):
    authed.app.state.fetcher = StubFetcher(text="Loading…", ok=False)
    response = add(authed, {"source_url": "https://example.com/js-only"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unreadable_page"
    assert "paste the text" in response.json()["error"]["message"]


def test_failed_extraction_can_be_retried(authed):
    authed.app.state.llm = FakeLLMProvider(default_json={"ok": True})
    created = add(authed, {"source_text": TEXT})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    run_id = created.json()["run_id"]

    failed = authed.get(f"/api/runs/{run_id}").json()
    assert failed["status"] == "failed"
    assert failed["steps"][0]["status"] == "failed"
    assert "job_extraction" in (failed["error"] or "") or "Reading the posting" in (failed["error"] or "")

    page = authed.get(f"/jobs/{job_id}")
    assert "run-error" in page.text

    authed.app.state.llm = FakeLLMProvider(FAKE_RESPONSES)
    retry = authed.post(f"/api/jobs/{job_id}/runs", headers=headers(authed))
    assert retry.status_code == 202
    resumed = authed.get(retry.json()["poll_url"]).json()
    assert resumed["status"] == "succeeded"


def test_queued_run_can_be_cancelled(authed, monkeypatch):
    import app.routes.jobs as jobs_routes

    monkeypatch.setattr(jobs_routes, "execute_run", lambda *args, **kwargs: None)
    created = add(authed, {"source_text": TEXT})
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    assert authed.get(f"/api/runs/{run_id}").json()["status"] == "queued"

    cancelled = authed.post(f"/api/runs/{run_id}/cancel", headers=headers(authed))
    assert cancelled.status_code == 202
    assert authed.get(f"/api/runs/{run_id}").json()["status"] == "cancelled"


def test_single_flight_returns_409(authed, monkeypatch):
    import app.routes.jobs as jobs_routes

    monkeypatch.setattr(jobs_routes, "execute_run", lambda *args, **kwargs: None)
    created = add(authed, {"source_text": TEXT})
    second = authed.post(f"/api/jobs/{created.json()['job_id']}/runs", headers=headers(authed))
    assert second.status_code == 409


def test_terminal_run_cannot_be_cancelled(authed):
    created = add(authed, {"source_text": TEXT})
    response = authed.post(f"/api/runs/{created.json()['run_id']}/cancel", headers=headers(authed))
    assert response.status_code == 409


def test_retry_uses_earlier_extraction_without_calling_the_model_twice(authed, settings):
    created = add(authed, {"source_text": TEXT})
    job_id = created.json()["job_id"]
    factory = get_session_factory(settings)
    with factory() as db:
        first = db.scalar(select(Run).where(Run.job_id == job_id))
        assert first.status == "succeeded"

    retried = authed.post(f"/api/jobs/{job_id}/runs", headers=headers(authed))
    assert retried.status_code == 202
    run = authed.get(retried.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert run["tokens_in"] == 0


def test_canonicalize_url_strips_tracking_and_fragment():
    assert (
        canonicalize_url("HTTPS://Example.com:443/role/?utm_campaign=x&gclid=y&team=ml#top")
        == "https://example.com/role/?team=ml"
    )
    with pytest.raises(ValueError):
        canonicalize_url("javascript:alert(1)")


def test_fingerprint_is_stable_and_case_insensitive():
    assert fingerprint("Acme, Inc.", "Senior ML Engineer", "Remote") == fingerprint(
        "acme", "senior ml engineer", "remote"
    )


def test_markdown_renderer_escapes_model_output():
    html = markdown_to_html("# Title\n\n- <script>alert(1)</script>\n\n**bold** text")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert '<h2 class="prose-h prose-h--title">Title</h2>' in html
    assert "<strong>bold</strong>" in html


def test_markdown_renderer_labels_sections_for_styling():
    html = markdown_to_html("## Delivery\n\n- Pause after the second sentence")
    assert '<h3 class="prose-h prose-h--delivery">Delivery</h3>' in html
    assert "<h3 class=\"prose-h prose-h--\">" not in html


def test_markdown_renderer_links_only_http_urls():
    html = markdown_to_html("- [News](https://example.com/a?b=1) and [bad](javascript:alert(1))")
    assert '<a href="https://example.com/a?b=1" target="_blank" rel="noopener noreferrer">News</a>' in html
    assert 'href="javascript' not in html.lower()
    assert "[bad](javascript:alert(1))" in html
    assert html.count("<a ") == 1


def test_markdown_renderer_escapes_link_text():
    html = markdown_to_html("[<img src=x onerror=alert(1)>](https://example.com)")
    assert "<img" not in html
    assert "&lt;img" in html
    assert 'href="https://example.com"' in html


def test_prose_helpers_keep_paragraph_breaks():
    from app.skills.text import clip_words, prose_text, strip_cliches

    assert prose_text("one  two\n\nthree\tfour") == "one two\n\nthree four"
    assert prose_text("a\n\n\n\nb") == "a\n\nb"
    assert strip_cliches("I am passionate about speech.\n\n  Then  more.  ") == (
        "I am about speech.\n\nThen more."
    )
    assert clip_words("One. Two.\n\nThree.", 10) == "One. Two.\n\nThree."
