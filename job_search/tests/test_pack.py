from __future__ import annotations

from io import BytesIO

from docx import Document
from sqlalchemy import select

from app.db import get_session_factory
from app.documents.letters import build_letter_docx, render_letter_pdf
from app.documents.resume import letter_filename
from app.models import Artifact, Job
from app.providers.llm.fake import FakeLLMProvider
from app.skills.fixtures import FAKE_COVER
from app.skills.registry import FAKE_RESPONSES
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _run(client):
    login(client)
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_cover_letter_is_one_page_and_names_the_company():
    content = build_letter_docx(FAKE_COVER, headline="Senior ML Engineer | Acme Speech")
    text = "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs)
    assert "LYLE OKOTH" in text
    assert "SENIOR ML ENGINEER | ACME SPEECH" in text
    assert "linkedin.com/in/lyle-okoth" in text
    assert "Dear Acme Speech team," in text
    assert "Sincerely," in text
    result = render_letter_pdf(
        content,
        FAKE_COVER,
        soffice_path="definitely-not-installed",
        headline="Senior ML Engineer | Acme Speech",
    )
    assert result.engine == "reportlab"
    assert result.pages == 1
    assert result.content.startswith(b"%PDF-")


def test_letter_filename_is_ats_safe():
    assert letter_filename("Acme Speech, GmbH", "Senior ML Engineer", 2, "pdf") == (
        "LYLE-OKOTH-ACME-SPEECH-GMBH-SENIOR-ML-ENGINEER-COVER-LETTER-v2.pdf"
    )


def test_full_pack_creates_cover_email_and_interview_artifacts(client, settings):
    job_id = _run(client)
    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, job_id)
        current = {
            artifact.kind: artifact
            for artifact in db.scalars(
                select(Artifact).where(Artifact.job_id == job.id, Artifact.is_current.is_(True))
            ).all()
        }
        assert job.status == "ready"
        assert {
            "cover_letter_pdf",
            "cover_letter_docx",
            "email",
            "company_research",
            "tell_me_about_yourself",
            "work_history",
            "proud_project",
            "technical_interview",
            "behavioral_interview",
        } <= set(current)
        assert current["cover_letter_pdf"].version == current["cover_letter_docx"].version == 1
        assert current["email"].meta_json["payload"]["subject"]
        assert "Acme Speech" in current["cover_letter_pdf"].meta_json["letter"]["greeting"]
        assert current["technical_interview"].meta_json["payload"]["questions"]
        cover_id = current["cover_letter_pdf"].id
        email_id = current["email"].id

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "Cover letter" in page.text
    assert "Application email" in page.text
    assert f"/api/artifacts/{cover_id}/preview" in page.text
    assert "Copy body" in page.text
    assert "Interview pack" in page.text

    assert client.get(f"/api/artifacts/{cover_id}/download").status_code == 200
    assert client.get(f"/api/artifacts/{email_id}/download").status_code == 200


def test_failed_optional_step_does_not_fail_the_run(client, settings):
    login(client)
    client.app.state.llm = FakeLLMProvider({**FAKE_RESPONSES, "email_writing": "{}"})
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202
    run = client.get(response.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert next(step for step in run["steps"] if step["skill"] == "email_writing")["status"] == "failed"
    with get_session_factory(settings)() as db:
        assert db.get(Job, response.json()["job_id"]).status == "reviewing"


def test_cover_letter_regenerates_independently(client, settings):
    job_id = _run(client)
    response = client.post(
        f"/api/jobs/{job_id}/regenerate", json={"skill": "cover_letter"}, headers=headers(client)
    )
    assert response.status_code == 202, response.text
    run = client.get(response.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert [step["skill"] for step in run["steps"]] == ["cover_letter"]
    with get_session_factory(settings)() as db:
        rows = db.scalars(
            select(Artifact)
            .where(Artifact.job_id == job_id, Artifact.kind == "cover_letter_pdf")
            .order_by(Artifact.version)
        ).all()
        assert [row.version for row in rows] == [1, 2]
        assert rows[0].is_current is False and rows[1].is_current is True
