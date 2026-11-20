from __future__ import annotations

import json

from sqlalchemy import create_engine, select, text

from app.db import _add_missing_columns, get_session_factory
from app.models import Artifact, InterviewQuestion, Job, Run
from app.providers.llm.fake import FakeLLMProvider
from tests.conftest import login

TEXT = """\
Senior Machine Learning Engineer at Acme Speech.
Own speech recognition quality across six languages and build evaluation tooling.
Must have Python, PyTorch and hands-on ASR experience. Remote within Europe.
"""


def headers(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


def _job(client) -> int:
    login(client)
    response = client.post("/api/jobs", json={"source_text": TEXT}, headers=headers(client))
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def test_study_page_renders_for_a_signed_in_user(client):
    login(client)
    response = client.get("/study")
    assert response.status_code == 200
    assert "Study workspace" in response.text
    assert "Generate questions" in response.text
    assert "data-study-player" in response.text


def test_study_questions_are_saved_without_a_job(client, settings):
    login(client)
    response = client.post(
        "/api/study/questions",
        json={
            "role": "ML platform engineer",
            "level": "Staff",
            "count": 3,
            "difficulty": "core",
            "focus": "production debugging",
        },
        headers=headers(client),
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["role"] == "ML platform engineer"
    assert payload["level"] == "Staff"
    assert payload["questions"]
    assert all(question["role"] == "ML platform engineer" for question in payload["questions"])
    assert all(question["level"] == "Staff" for question in payload["questions"])

    factory = get_session_factory(settings)
    with factory() as db:
        rows = db.scalars(select(InterviewQuestion)).all()
        assert rows
        assert all(row.job_id is None for row in rows)

    listed = client.get("/api/study/questions")
    assert listed.status_code == 200
    assert len(listed.json()["questions"]) == len(payload["questions"])


def test_study_audio_returns_a_wav(client):
    login(client)
    response = client.post(
        "/api/study/audio",
        json={"text": "Explain the bias variance trade-off.", "role": "question"},
        headers=headers(client),
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "audio/wav"
    assert response.content.startswith(b"RIFF")
    assert len(response.content) > 44

    # A voice saved for another provider must not fail playback.
    fallback = client.post(
        "/api/study/audio",
        json={
            "text": "Explain the bias variance trade-off.",
            "role": "answer",
            "voice": "elevenlabs-voice-that-does-not-exist-here",
        },
        headers=headers(client),
    )
    assert fallback.status_code == 200, fallback.text
    assert fallback.content.startswith(b"RIFF")


def test_delete_job_removes_rows_and_files(client, settings):
    job_id = _job(client)
    assert f'data-delete-job="{job_id}"' in client.get("/jobs").text
    detail = client.get(f"/jobs/{job_id}").text
    assert "Delete job" in detail
    assert "data-fill-missing" in detail
    assert "data-collapsible" in detail
    assert "collapsible.js" in detail

    folder = settings.artifacts_dir / f"job-{job_id}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "leftover.txt").write_text("generated output", encoding="utf-8")

    response = client.delete(f"/api/jobs/{job_id}", headers=headers(client))
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True
    assert not folder.exists()

    factory = get_session_factory(settings)
    with factory() as db:
        assert db.get(Job, job_id) is None
        assert db.scalars(select(Artifact).where(Artifact.job_id == job_id)).all() == []


def test_delete_job_refuses_while_a_run_is_in_flight(client, settings):
    job_id = _job(client)
    factory = get_session_factory(settings)
    with factory() as db:
        run = Run(job_id=job_id, kind="prepare", status="running", total_steps=1)
        db.add(run)
        db.commit()

    response = client.delete(f"/api/jobs/{job_id}", headers=headers(client))
    assert response.status_code == 409
    assert "cancel" in response.json()["error"]["message"].lower()


def test_fill_missing_queues_only_absent_artifacts(client, settings):
    job_id = _job(client)
    factory = get_session_factory(settings)
    with factory() as db:
        artifact = db.scalar(
            select(Artifact).where(
                Artifact.job_id == job_id,
                Artifact.kind == "low_level_design",
                Artifact.is_current.is_(True),
            )
        )
        assert artifact is not None
        db.delete(artifact)
        db.commit()

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert "Not generated yet" in page.text

    response = client.post(f"/api/jobs/{job_id}/backfill", headers=headers(client))
    assert response.status_code == 202, response.text
    assert response.json()["skills"] == ["low_level_design"]


def test_additive_columns_upgrade_an_older_database(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE interview_questions ("
                "id INTEGER PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL)"
            )
        )
    _add_missing_columns(engine)
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(interview_questions)")}
    assert {"role", "level", "follow_up_answers_json"} <= columns
    engine.dispose()


def test_follow_up_answers_are_written_once_and_cached(client, settings):
    login(client)
    with get_session_factory(settings)() as db:
        question = InterviewQuestion(
            origin="practice",
            topic="Streaming",
            difficulty="core",
            question="How would you bound latency in a streaming ASR service?",
            answer="I would set a first-audio budget and measure every stage against it.",
            follow_ups_json=["What changes under load?", "How would you test it?"],
        )
        db.add(question)
        db.commit()
        question_id = question.id

    answers = {
        "answers": [
            {"question": "What changes under load?", "answer": "I would shed optional work first."},
            {"question": "How would you test it?", "answer": "I would replay recorded traffic."},
        ]
    }
    client.app.state.llm = FakeLLMProvider({"interview_follow_ups": json.dumps(answers)})
    response = client.post(
        f"/api/interview/questions/{question_id}/follow-up-answers",
        headers=headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()["answers"]
    assert [item["answer"] for item in body] == [
        "I would shed optional work first.",
        "I would replay recorded traffic.",
    ]

    # A second open must not call the model again.
    client.app.state.llm = FakeLLMProvider(default_json={"answers": []})
    cached = client.post(
        f"/api/interview/questions/{question_id}/follow-up-answers",
        headers=headers(client),
    )
    assert cached.status_code == 200
    assert cached.json()["answers"] == body
