from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Prepare a SQLite database for development.

    Alembic owns the schema once its version table exists, so startup never adds
    tables behind the migration runner's back. A brand-new database is created
    from metadata and stamped at head; subsequent releases move it with
    ``alembic upgrade head``. Postgres deployments use Alembic directly.
    """
    from app import models  # noqa: F401  (register mappers)

    if inspect(engine).has_table("alembic_version"):
        return

    Base.metadata.create_all(bind=engine)
    _stamp_head()


def _stamp_head() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.stamp(config, "head")
