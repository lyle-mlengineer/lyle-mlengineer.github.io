from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.models import InterviewQuestion
from tests.conftest import login

SOURCE = """\
# Streaming ASR notes

A streaming session needs an explicit state machine. Audio frames enter a bounded
queue, and a writer task owns the model call. When the queue is full the session
applies backpressure instead of growing memory. Cancellation closes the queue and
waits for the writer to acknowledge it.
"""


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _ask(client, **body) -> dict:
    response = client.post("/api/ask", json=body, headers=headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_ask_page_is_signed_in_only(client):
    anon = client.get("/ask", follow_redirects=False)
    assert anon.status_code == 303
    assert anon.headers["location"].startswith("/login")

    login(client)
    page = client.get("/ask")
    assert page.status_code == 200
    assert "Ask workspace" in page.text
    # The subject list and the answer card the pre-existing section uses.
    assert "Low-level design" in page.text
    assert "Work history" in page.text
    assert "About yourself" in page.text
    assert "data-ask-form" in page.text
    assert "data-ask-result" in page.text
    assert 'href="/ask"' in page.text


def test_ask_answers_without_a_job_and_saves_the_answer(client, settings):
    login(client)
    body = _ask(
        client,
        question="How would you add backpressure to a streaming ASR session?",
        topic="system",
        role="ML platform engineer",
        level="Staff",
    )
    assert body["answer"]
    assert body["topic"] == "System design"
    assert body["topic_key"] == "system"
    assert body["confidence"] in {"high", "medium", "low"}

    factory = get_session_factory(settings)
    with factory() as db:
        rows = db.scalars(select(InterviewQuestion)).all()
        assert len(rows) == 1
        assert rows[0].job_id is None
        assert rows[0].origin == "answer"
        assert rows[0].topic == "System design"
        assert rows[0].role == "ML platform engineer"
        assert rows[0].level == "Staff"

    listed = client.get("/api/ask/questions")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["questions"][0]["question"].startswith("How would you add backpressure")

    # The saved answer renders on the page it was asked from.
    page = client.get("/ask")
    assert "How would you add backpressure" in page.text


def test_ask_uses_the_selected_subject_shape(client):
    login(client)
    seen: list[str] = []
    original = client.app.state.llm

    class Spy:
        name = original.name
        models = original.models

        def model_for(self, tier):
            return original.model_for(tier)

        def complete(self, *args, **kwargs):  # pragma: no cover - not used here
            return original.complete(*args, **kwargs)

        def complete_json(self, messages, schema, **kwargs):
            seen.append(messages[0].content)
            return original.complete_json(messages, schema, **kwargs)

        def health(self):
            return True

    client.app.state.llm = Spy()
    try:
        _ask(client, question="Tell me about yourself.", topic="about")
        _ask(client, question="How would you design object storage for audio?", topic="low_level")
    finally:
        client.app.state.llm = original

    assert "ninety-second 'tell me about yourself'" in seen[0]
    assert "low-level design answer" in seen[1]


def test_ask_unknown_topic_falls_back_to_technical(client):
    login(client)
    body = _ask(client, question="Explain the bias variance trade-off.", topic="nonsense")
    assert body["topic"] == "Technical"
    assert body["topic_key"] == "technical"


def test_ask_rejects_an_empty_question(client):
    login(client)
    response = client.post("/api/ask", json={"question": "hi"}, headers=headers(client))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_ask_needs_csrf(client):
    login(client)
    response = client.post("/api/ask", json={"question": "Explain retrieval augmented generation."})
    assert response.status_code == 403


def test_asks_stay_out_of_the_study_workspace(client):
    login(client)
    _ask(client, question="What is a token bucket?", topic="technical")

    study = client.get("/api/study/questions")
    assert study.status_code == 200
    assert study.json()["questions"] == []

    client.post(
        "/api/study/questions",
        json={"role": "ML engineer", "level": "Senior", "count": 2},
        headers=headers(client),
    )
    study = client.get("/api/study/questions").json()["questions"]
    assert study and all(row["origin"] != "answer" for row in study)


def test_an_ask_can_be_deleted_from_its_own_history(client):
    login(client)
    body = _ask(client, question="How do you evaluate a speech model?", topic="technical")

    response = client.delete(
        f"/api/interview/questions/{body['id']}",
        headers=headers(client),
    )
    assert response.status_code == 200
    assert client.get("/api/ask/questions").json()["count"] == 0


def test_ask_grounds_in_uploaded_documents(client):
    login(client)
    uploaded = client.post(
        "/api/interview/sources",
        data={"title": "Streaming notes", "text": SOURCE},
        headers=headers(client),
    )
    assert uploaded.status_code == 201, uploaded.text

    body = _ask(
        client,
        question="How does a bounded queue apply backpressure?",
        topic="technical",
    )
    assert any("Streaming notes" in citation for citation in body["citations"])
