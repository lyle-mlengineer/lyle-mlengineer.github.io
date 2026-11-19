from __future__ import annotations

from app import domain
from app.db import (
    get_setting,
    init_db,
    session_scope,
    set_setting,
    sweep_expired_sessions,
    sweep_interrupted_runs,
)
from app.models import Run, SchemaVersion, User
from app.security import hash_password, verify_password


def test_schema_creation_is_idempotent(settings):
    init_db(settings)
    init_db(settings)
    with session_scope(settings) as session:
        versions = session.query(SchemaVersion).all()
        assert len(versions) == 1


def test_password_hash_round_trip():
    digest = hash_password("correct horse battery staple")
    assert digest.startswith("$argon2id$")
    assert verify_password(digest, "correct horse battery staple")
    assert not verify_password(digest, "wrong")


def test_settings_table_round_trip(settings):
    set_setting(settings, "llm_provider", "groq")
    assert get_setting(settings, "llm_provider") == "groq"
    assert get_setting(settings, "missing", "fallback") == "fallback"


def test_interrupted_runs_are_marked_on_startup(settings):
    with session_scope(settings) as session:
        user = session.query(User).first()
        assert user is not None
        from app.models import Company, Job

        company = Company(name="Acme", slug="acme", created_at="2026-01-01T00:00:00Z",
                          updated_at="2026-01-01T00:00:00Z")
        session.add(company)
        session.flush()
        job = Job(company_id=company.id, title="ML Engineer", slug="ml-engineer",
                  source_type="text", raw_text="text", fingerprint="b" * 40)
        session.add(job)
        session.flush()
        session.add_all(
            [
                Run(job_id=job.id, kind="full", status="running"),
                Run(job_id=job.id, kind="cv", status="queued"),
                Run(job_id=job.id, kind="full", status="succeeded"),
            ]
        )

    marked = sweep_interrupted_runs(settings)
    assert marked == 2
    with session_scope(settings) as session:
        statuses = sorted(run.status for run in session.query(Run).all())
        assert statuses == ["interrupted", "interrupted", "succeeded"]


def test_sweep_expired_sessions(settings):
    from app.models import AuthSession

    with session_scope(settings) as session:
        user = session.query(User).first()
        session.add(
            AuthSession(
                id="deadbeef",
                user_id=user.id,
                csrf_token="x",
                created_at="2020-01-01T00:00:00Z",
                expires_at="2020-01-01T00:00:00Z",
                last_seen_at="2020-01-01T00:00:00Z",
            )
        )
    assert sweep_expired_sessions(settings) == 1
    with session_scope(settings) as session:
        assert session.query(AuthSession).count() == 0


def test_status_transitions_are_forward_only():
    assert domain.can_transition("preparing", "ready")
    assert domain.can_transition("ready", "applied")
    assert domain.can_transition("applied", "interviewing")
    assert not domain.can_transition("discovered", "offer")
    assert not domain.can_transition("offer", "ready")
    assert domain.can_transition("archived", "ready")
    assert all(target in domain.JOB_STATUSES for targets in domain.STATUS_TRANSITIONS.values() for target in targets)


def test_skill_manifest_is_ordered_and_well_formed():
    names = [skill["name"] for skill in domain.SKILLS]
    assert len(names) == len(set(names)) == 11
    for skill in domain.SKILLS:
        for required in skill["requires"]:
            assert required in names
        assert skill["weight"] > 0
