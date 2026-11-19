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

FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS portfolio_fts USING fts5(
  text, heading, doc_title,
  content='portfolio_chunks', content_rowid='id', tokenize='porter unicode61'
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


def init_db(settings: Settings) -> None:
    engine = get_engine(settings)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(FTS_DDL)
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
