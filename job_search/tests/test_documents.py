from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from sqlalchemy import select

from app.db import get_session_factory
from app.documents.cv_docx import build_cv_docx
from app.documents.cv_pdf import pdf_page_count, render_pdf
from app.documents.resume import artifact_filename
from app.models import Artifact, Job
from app.rag.grounding import check_numbers
from app.skills.cv_writing import _corpus, _scrub
from app.skills.fixtures import FAKE_CV
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


@pytest.fixture()
def authed(client):
    login(client)
    return client


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _run_job(client) -> int:
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_docx_contains_the_whole_resume():
    content = build_cv_docx(FAKE_CV)
    text = _docx_text(content)
    assert content.startswith(b"PK")
    assert "LYLE OKOTH" in text
    assert FAKE_CV["headline"] in text
    for job in FAKE_CV["experience"]:
        assert job["company"] in text
        assert job["title"] in text
        for bullet in job["bullets"]:
            assert bullet[:60] in text
    for group in FAKE_CV["skill_groups"]:
        assert group["name"] in text
    assert "EDUCATION" in text and "CERTIFICATIONS" in text


def test_pdf_is_two_pages_and_uses_the_fallback_when_libreoffice_is_missing():
    docx = build_cv_docx(FAKE_CV)
    result = render_pdf(docx, FAKE_CV, soffice_path="definitely-not-installed")
    assert result.engine == "reportlab"
    assert result.content.startswith(b"%PDF-")
    assert len(result.content) > 10_000
    assert 1 <= result.pages <= 2
    assert pdf_page_count(result.content) == result.pages


def test_readyz_names_the_pdf_engine(client):
    components = client.get("/readyz").json()["components"]
    assert components["pdf_engine"] == "reportlab"


def test_filename_is_ats_safe_and_versioned():
    name = artifact_filename("Acme Speech, GmbH", "Senior ML Engineer / Speech", 2, "pdf")
    assert name == "LYLE-OKOTH-ACME-SPEECH-GMBH-SENIOR-ML-ENGINEER-SPEECH-CV-v2.pdf"


def test_numbers_absent_from_the_portfolio_are_scrubbed():
    corpus = _corpus(Path("data/portfolio"))
    dirty = "Cut latency 35% on 9,999 clips; kept WER at 11.8% across 1,240 hours."
    clean = _scrub(dirty, corpus)
    assert "35%" not in clean and "9,999" not in clean
    assert "11.8%" in clean and "1,240" in clean
    assert "measurably" in clean
    assert check_numbers(clean, corpus) == []


def test_pipeline_cv_is_grounded_and_downloadable(authed, settings):
    job_id = _run_job(authed)
    factory = get_session_factory(settings)
    with factory() as db:
        job = db.get(Job, job_id)
        pdf = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job.id, Artifact.kind == "cv_pdf", Artifact.is_current.is_(True)
            )
        )
        docx = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job.id, Artifact.kind == "cv_docx", Artifact.is_current.is_(True)
            )
        )
        assert pdf and docx and pdf.version == docx.version == 1
        assert pdf.meta_json["resume"]["headline"]
        assert pdf.meta_json["pages"] <= 2
        assert pdf.path and docx.path and Path(pdf.path).is_file() and Path(docx.path).is_file()
        assert "ACME-SPEECH" in Path(pdf.path).name
        content = Path(pdf.path).read_bytes()
        text = _docx_text(Path(docx.path).read_bytes())
        assert check_numbers(text, _corpus(settings.portfolio_dir)) == []
        pdf_id, docx_id = pdf.id, docx.id

    download = authed.get(f"/api/artifacts/{pdf_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert content == download.content
    assert "attachment" in download.headers["content-disposition"]

    preview = authed.get(f"/api/artifacts/{pdf_id}/preview")
    assert preview.status_code == 200
    assert "inline" in preview.headers["content-disposition"]
    assert preview.headers["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in preview.headers["content-security-policy"]

    docx_download = authed.get(f"/api/artifacts/{docx_id}/download")
    assert docx_download.status_code == 200
    assert docx_download.content.startswith(b"PK")

    page = authed.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "Tailored CV" in page.text
    assert f"/api/artifacts/{pdf_id}/preview" in page.text
    assert "Regenerate" in page.text
    # The CV button must carry the delegated hook the page script binds to.
    assert 'data-regenerate data-skill="cv_writing"' in page.text


def test_regenerate_creates_v2_and_keeps_v1_downloadable(authed, settings):
    job_id = _run_job(authed)
    factory = get_session_factory(settings)
    with factory() as db:
        v1 = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job_id, Artifact.kind == "cv_pdf", Artifact.is_current.is_(True)
            )
        )
        v1_id, v1_path = v1.id, v1.path

    response = authed.post(
        f"/api/jobs/{job_id}/regenerate", json={"skill": "cv_writing"}, headers=headers(authed)
    )
    assert response.status_code == 202, response.text
    run = authed.get(response.json()["poll_url"]).json()
    assert run["status"] == "succeeded"
    assert [step["skill"] for step in run["steps"]] == ["cv_writing"]

    with factory() as db:
        rows = db.scalars(
            select(Artifact)
            .where(Artifact.job_id == job_id, Artifact.kind == "cv_pdf")
            .order_by(Artifact.version)
        ).all()
        assert [row.version for row in rows] == [1, 2]
        assert rows[0].is_current is False and rows[1].is_current is True
        assert Path(v1_path).is_file()

    old = authed.get(f"/api/artifacts/{v1_id}/download")
    assert old.status_code == 200
    page = authed.get(f"/jobs/{job_id}")
    assert "Version 2" in page.text


def test_download_requires_login(client):
    assert client.get("/api/artifacts/1/download").status_code == 401
    assert client.get("/api/artifacts/1/preview").status_code == 401


def test_regenerate_requires_csrf_and_known_skill(authed):
    job_id = _run_job(authed)
    no_csrf = authed.post(f"/api/jobs/{job_id}/regenerate", json={"skill": "cv_writing"})
    assert no_csrf.status_code == 403
    unknown = authed.post(
        f"/api/jobs/{job_id}/regenerate", json={"skill": "not_a_skill"}, headers=headers(authed)
    )
    assert unknown.status_code == 422
    extraction = authed.post(
        f"/api/jobs/{job_id}/regenerate", json={"skill": "job_extraction"}, headers=headers(authed)
    )
    assert extraction.status_code == 422
