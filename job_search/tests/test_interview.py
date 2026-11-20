from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.interview.sources import search_source_chunks
from app.models import InterviewQuestion, InterviewSource, LlmCall
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
We are looking for a senior engineer to own speech recognition quality across six languages.
You will build evaluation tooling, fine-tune Whisper models and work with product teams.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""

SOURCE = """\
# Streaming ASR notes

A streaming session needs an explicit state machine. Audio frames enter a bounded
queue, and a writer task owns the model call. When the queue is full the session
applies backpressure instead of growing memory. Cancellation closes the queue and
waits for the writer to acknowledge it.

Evaluation should use a locked test set with a content hash. The gate compares a
candidate model with the stored baseline and reports every language slice, not one
average. A regression beyond the budget fails the release.
"""

def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _job(client) -> int:
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def _upload(client, *, title: str = "Streaming notes", text: str = SOURCE) -> dict:
    response = client.post(
        "/api/interview/sources",
        data={"title": title, "text": text},
        headers=headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()["source"]


def test_upload_text_source_is_chunked_and_searchable(client, settings):
    login(client)
    source = _upload(client)
    assert source["kind"] == "text"
    assert source["chars"] >= len(SOURCE) - 20
    assert source["chunks"] >= 1

    listing = client.get("/api/interview/sources").json()
    assert listing["count"] == 1
    assert listing["sources"][0]["title"] == "Streaming notes"

    with get_session_factory(settings)() as db:
        stored = db.scalar(select(InterviewSource).where(InterviewSource.id == source["id"]))
        assert stored is not None
        assert stored.text.startswith("# Streaming ASR notes")
        chunks = search_source_chunks(db, "bounded queue backpressure", limit=3)
        assert chunks
        assert chunks[0].source_id == stored.id


def test_duplicate_source_is_rejected(client, settings):
    login(client)
    _upload(client)
    repeated = client.post(
        "/api/interview/sources",
        data={"title": "Another name", "text": SOURCE},
        headers=headers(client),
    )
    assert repeated.status_code == 422
    assert "already saved" in repeated.json()["error"]["message"]


def test_practice_set_is_saved_and_attributed(client, settings):
    login(client)
    job_id = _job(client)
    response = client.post(
        f"/api/jobs/{job_id}/interview/practice",
        json={"count": 3, "difficulty": "mixed", "seed": 42},
        headers=headers(client),
    )
    assert response.status_code == 201, response.text
    questions = response.json()["questions"]
    assert len(questions) == 3
    assert all(question["answer"] for question in questions)
    assert all(question["difficulty"] in {"warm-up", "core", "deep"} for question in questions)

    with get_session_factory(settings)() as db:
        rows = db.scalars(select(InterviewQuestion).where(InterviewQuestion.job_id == job_id)).all()
        assert len(rows) == 3
        assert {row.origin for row in rows} == {"practice"}
        calls = db.scalars(
            select(LlmCall).where(LlmCall.job_id == job_id, LlmCall.skill == "interview_practice")
        ).all()
        assert len(calls) == 1

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "Random drills" in page.text
    assert "Interview sources" in page.text
    assert "Find an answer" in page.text


def test_questions_from_a_source_cite_it_and_answer_lookup_uses_it(client, settings):
    login(client)
    job_id = _job(client)
    source = _upload(client)

    response = client.post(
        f"/api/interview/sources/{source['id']}/questions",
        json={"job_id": job_id, "count": 2, "seed": 7},
        headers=headers(client),
    )
    assert response.status_code == 201, response.text
    questions = response.json()["questions"]
    assert questions
    assert all(question["source_title"] == "Streaming notes" for question in questions)
    assert questions[0]["citations"]

    answer = client.post(
        f"/api/jobs/{job_id}/interview/answer",
        json={"question": "How does backpressure work in a streaming session?"},
        headers=headers(client),
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert "provider seam" in body["answer"]
    assert body["citations"]
    assert "Streaming notes" in body["citations"][0]


def test_deleting_a_source_removes_its_index_rows(client, settings):
    login(client)
    _upload(client)
    source_id = client.get("/api/interview/sources").json()["sources"][0]["id"]

    response = client.delete(f"/api/interview/sources/{source_id}", headers=headers(client))
    assert response.status_code == 200
    assert client.get("/api/interview/sources").json()["count"] == 0

    with get_session_factory(settings)() as db:
        assert not search_source_chunks(db, "backpressure queue", limit=3)
