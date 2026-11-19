"""SQLAlchemy 2.0 models — the single definition of Skipper's data.

Conventions
-----------
* Timestamps are UTC ISO-8601 strings ending in ``Z``. String columns keep the
  format stable across SQLite, JSON exports and Jinja rendering; lexical order is
  chronological order.
* Enum-ish columns are plain strings; the allowed values live in ``app/domain.py``
  and are enforced in the service layer.
* JSON columns use SQLAlchemy's ``JSON`` type so callers get dicts/lists, not text.
* The FTS5 index (``portfolio_fts``) is a virtual table and is created with raw
  DDL in ``app/db.py`` — it is an index, not an entity.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- accounts


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
    last_login_at: Mapped[str | None] = mapped_column(String(32))

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(cookie token)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_hash: Mapped[str | None] = mapped_column(String(32))

    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (Index("idx_sessions_user", "user_id"),)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    attempted_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    __table_args__ = (Index("idx_login_attempts", "ip_hash", "username", "attempted_at"),)


# ---------------------------------------------------------------- companies


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String(500))
    domain: Mapped[str | None] = mapped_column(String(200), unique=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    headcount: Mapped[str | None] = mapped_column(String(60))
    hq: Mapped[str | None] = mapped_column(String(160))
    founded: Mapped[str | None] = mapped_column(String(20))
    summary: Mapped[str | None] = mapped_column(Text)
    research_json: Mapped[dict | None] = mapped_column(JSON)
    researched_at: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow, onupdate=utcnow, nullable=False)

    jobs: Mapped[list[Job]] = relationship(back_populates="company")
    sources: Mapped[list[Source]] = relationship(back_populates="company")


# ---------------------------------------------------------------- jobs


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(240), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    work_mode: Mapped[str | None] = mapped_column(String(20))
    employment_type: Mapped[str | None] = mapped_column(String(40))
    seniority: Mapped[str | None] = mapped_column(String(40))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(8))
    salary_period: Mapped[str | None] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # website|board|text
    source_url: Mapped[str | None] = mapped_column(String(2048))
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text)
    summary_md: Mapped[str | None] = mapped_column(Text)
    extract_json: Mapped[dict | None] = mapped_column(JSON)
    keywords_json: Mapped[list | None] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    posted_at: Mapped[str | None] = mapped_column(String(32))
    deadline: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="discovered", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    next_action: Mapped[str | None] = mapped_column(String(240))
    next_action_at: Mapped[str | None] = mapped_column(String(32))
    archived_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow, onupdate=utcnow, nullable=False)

    company: Mapped[Company | None] = relationship(back_populates="jobs")
    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True,
        order_by="JobEvent.created_at.desc()",
    )
    runs: Mapped[list[Run]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Run.created_at.desc()",
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True,
    )
    sources: Mapped[list[Source]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_jobs_status", "status", "updated_at"),
        Index("idx_jobs_company", "company_id"),
    )


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # created|status|artifact|note|run
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="events")

    __table_args__ = (Index("idx_job_events_job", "job_id", "created_at"),)


# ---------------------------------------------------------------- runs


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(60))
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(40))
    model_large: Mapped[str | None] = mapped_column(String(120))
    model_small: Mapped[str | None] = mapped_column(String(120))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="runs")
    steps: Mapped[list[RunStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True,
        order_by="RunStep.ordinal",
    )
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="run")

    __table_args__ = (
        Index("idx_runs_job", "job_id", "created_at"),
        Index("idx_runs_status", "status"),
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    skill: Mapped[str] = mapped_column(String(60), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    output_json: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)

    run: Mapped[Run] = relationship(back_populates="steps")

    __table_args__ = (
        UniqueConstraint("run_id", "skill", name="uq_run_steps_run_skill"),
        Index("idx_run_steps_run", "run_id", "ordinal"),
    )


# ---------------------------------------------------------------- artifacts


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)  # md|pdf|docx|json|txt
    path: Mapped[str | None] = mapped_column(String(500))
    bytes: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    content_md: Mapped[str | None] = mapped_column(Text)
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    edited_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="artifacts")
    run: Mapped[Run | None] = relationship(back_populates="artifacts")

    __table_args__ = (
        UniqueConstraint("job_id", "kind", "version", name="uq_artifacts_job_kind_version"),
        Index("idx_artifacts_current", "job_id", "kind", "is_current"),
    )


# ---------------------------------------------------------------- provenance


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    kind: Mapped[str | None] = mapped_column(String(20))  # posting|company_page|search_result
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    job: Mapped[Job | None] = relationship(back_populates="sources")
    company: Mapped[Company | None] = relationship(back_populates="sources")

    __table_args__ = (
        Index("idx_sources_job", "job_id"),
        Index("idx_sources_company", "company_id"),
    )


# ---------------------------------------------------------------- caches


class SearchCache(Base):
    __tablename__ = "search_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    results_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (UniqueConstraint("provider", "query_hash", name="uq_search_cache"),)


class LlmCache(Base):
    __tablename__ = "llm_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("provider", "model", "prompt_hash", name="uq_llm_cache"),)


# ---------------------------------------------------------------- portfolio RAG


class PortfolioDoc(Base):
    __tablename__ = "portfolio_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(240))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)

    chunks: Mapped[list[PortfolioChunk]] = relationship(
        back_populates="doc", cascade="all, delete-orphan", passive_deletes=True,
        order_by="PortfolioChunk.ordinal",
    )


class PortfolioChunk(Base):
    __tablename__ = "portfolio_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_docs.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(240))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    est_tokens: Mapped[int | None] = mapped_column(Integer)

    doc: Mapped[PortfolioDoc] = relationship(back_populates="chunks")


# ---------------------------------------------------------------- settings


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[str] = mapped_column(String(32), default=utcnow, nullable=False)
