from __future__ import annotations

from app.db import session_scope
from app.models import Job, JobEvent


def test_login_returns_cookie_and_me(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "lyle", "password": "test-password-123"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 204
    assert "skipper_session=" in response.headers.get("set-cookie", "")

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "lyle"
    assert body["csrf_token"]
    assert body["expires_at"].endswith("Z")


def test_me_requires_a_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_rejects_cross_origin(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "lyle", "password": "test-password-123"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403


def test_logout_requires_csrf(client):
    client.post(
        "/api/auth/login",
        json={"username": "lyle", "password": "test-password-123"},
        headers={"Origin": "http://testserver"},
    )
    assert client.post("/api/auth/logout").status_code == 403

    csrf = client.get("/api/auth/me").json()["csrf_token"]
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected(client, settings):
    client.post(
        "/api/auth/login",
        json={"username": "lyle", "password": "test-password-123"},
        headers={"Origin": "http://testserver"},
    )
    assert client.get("/api/auth/me").status_code == 200

    with session_scope(settings) as session:
        from app.models import AuthSession

        for row in session.query(AuthSession).all():
            row.expires_at = "2000-01-01T00:00:00Z"

    assert client.get("/api/auth/me").status_code == 401


def test_job_and_event_rows_round_trip(settings):
    """The ORM contract the ingestion phase will build on."""
    with session_scope(settings) as session:
        job = Job(
            title="Machine Learning Engineer",
            slug="ml-engineer-acme",
            source_type="text",
            raw_text="We are hiring an ML engineer.",
            fingerprint="a" * 40,
        )
        session.add(job)
        session.flush()
        session.add(JobEvent(job_id=job.id, event_type="created", to_status="discovered"))
        job_id = job.id

    with session_scope(settings) as session:
        stored = session.get(Job, job_id)
        assert stored is not None
        assert stored.status == "discovered"
        assert stored.extract_json is None
        events = session.query(JobEvent).filter_by(job_id=job_id).all()
        assert len(events) == 1
