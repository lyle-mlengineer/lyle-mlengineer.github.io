"""Database engine, sessions and bootstrap.

SQLAlchemy 2.0 with SQLite in WAL mode. One engine per database path (the tests
use a temp file, production uses ``var/skipper.db``), one session per request or
background task.

Schema lifecycle: ``Base.metadata.create_all`` is the pre-release mechanism. Once
v1 is deployed, every further change must ship as an Alembic revision — see design
§10.4. The FTS5 index is a virtual table and is created with raw DDL because it is
an index, not a mapped entity.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, delete, event, select
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base, SchemaVersion, Setting, utcnow

logger = logging.getLogger("skipper.db")

SCHEMA_VERSION = 1

# ``create_all`` creates missing tables but never alters existing ones. Additive
# columns are applied here so a running database keeps its rows when a new
# optional field is introduced. Destructive changes still need a migration.
ADDITIVE_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "interview_questions": (
        ("role", "VARCHAR(120)"),
        ("level", "VARCHAR(40)"),
        ("follow_up_answers_json", "JSON"),
    ),
    "portfolio_chunks": (("doc_title", "VARCHAR(240)"),),
}

FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS portfolio_fts USING fts5(
  text, heading, doc_title,
  content='portfolio_chunks', content_rowid='id', tokenize='porter unicode61'
);
"""

# Interview sources are written and deleted by ``app.interview.sources``; the
# index is contentless because the source title lives on the parent row.
INTERVIEW_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS interview_source_fts USING fts5(
  text, heading, source_title, tokenize='porter unicode61'
);
"""

_ENGINES: dict[str, Engine] = {}
_FACTORIES: dict[str, sessionmaker[Session]] = {}


def _apply_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_engine(settings: Settings) -> Engine:
    key = str(Path(settings.db_path).resolve())
    engine = _ENGINES.get(key)
    if engine is None:
        settings.ensure_runtime_dirs()
        engine = create_engine(
            f"sqlite+pysqlite:///{key}",
            connect_args={"check_same_thread": False, "timeout": 10},
            pool_pre_ping=True,
        )
        event.listen(engine, "connect", _apply_pragmas)
        _ENGINES[key] = engine
    return engine


def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    key = str(Path(settings.db_path).resolve())
    factory = _FACTORIES.get(key)
    if factory is None:
        factory = sessionmaker(bind=get_engine(settings), autoflush=False, expire_on_commit=False)
        _FACTORIES[key] = factory
    return factory


@contextmanager
def session_scope(settings: Settings) -> Iterator[Session]:
    """Transactional scope for background work and startup tasks."""
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _add_missing_columns(engine: Engine) -> None:
    """Apply additive column changes to a database created by an older build."""
    with engine.begin() as conn:
        for table, columns in ADDITIVE_COLUMNS.items():
            existing = {
                str(row[1]) for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:
                continue
            for name, ddl in columns:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _rebuild_changed_fts(engine: Engine) -> None:
    """Drop derived FTS tables whose columns changed; they are rebuilt at startup.

    ``CREATE VIRTUAL TABLE IF NOT EXISTS`` silently keeps an older layout, which
    then fails every insert with "no such column". The index is derived data, so
    dropping it is safe: ``reindex()`` repopulates it on the next startup.
    """
    expected = {
        "portfolio_fts": ("text", "heading", "doc_title"),
        "interview_source_fts": ("text", "heading", "source_title"),
    }
    with engine.begin() as conn:
        for table, columns in expected.items():
            existing = tuple(
                str(row[1]) for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            )
            if existing and existing != columns:
                conn.exec_driver_sql(f"DROP TABLE {table}")
                logger.warning("Rebuilding %s: schema changed from %s", table, existing)


def init_db(settings: Settings) -> None:
    engine = get_engine(settings)
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    _rebuild_changed_fts(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(FTS_DDL)
        conn.exec_driver_sql(INTERVIEW_FTS_DDL)
    with session_scope(settings) as session:
        latest = session.execute(select(SchemaVersion).order_by(SchemaVersion.version.desc())).scalars().first()
        if latest is None:
            session.add(SchemaVersion(version=SCHEMA_VERSION, applied_at=utcnow()))
        elif latest.version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema v{latest.version} is newer than this build (v{SCHEMA_VERSION}). "
                "Upgrade the app or restore a matching backup."
            )


def dispose_engines() -> None:
    """Test helper: close pooled connections so temp databases can be deleted."""
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
    _FACTORIES.clear()


def sweep_expired_sessions(settings: Settings) -> int:
    from .models import AuthSession

    with session_scope(settings) as session:
        result = session.execute(delete(AuthSession).where(AuthSession.expires_at <= utcnow()))
        return int(result.rowcount or 0)


def sweep_interrupted_runs(settings: Settings) -> int:
    """Runs cannot survive a restart; say so instead of lying about progress."""
    from .models import Run

    with session_scope(settings) as session:
        runs = session.execute(
            select(Run).where(Run.status.in_(("queued", "running")))
        ).scalars().all()
        for run in runs:
            run.status = "interrupted"
            run.error = "The server restarted during this run."
            run.finished_at = utcnow()
        return len(runs)


def get_setting(settings: Settings, key: str, default: str | None = None) -> str | None:
    with session_scope(settings) as session:
        row = session.get(Setting, key)
        return row.value if row else default


def set_setting(settings: Settings, key: str, value: str) -> None:
    with session_scope(settings) as session:
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value, updated_at=utcnow()))
        else:
            row.value = value
            row.updated_at = utcnow()
