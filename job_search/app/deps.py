"""Request-scoped dependencies: settings, ORM session, authentication, CSRF."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import get_session_factory
from .security import load_session


def get_db() -> Iterator[Session]:
    session = get_session_factory(get_settings())()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_app_settings() -> Settings:
    return get_settings()


def current_session(request: Request, db: Session) -> dict[str, Any] | None:
    token = request.cookies.get(get_settings().session_cookie)
    return load_session(db, token)


def require_csrf(request: Request, session: dict[str, Any]) -> None:
    """Double-submit CSRF check for state-changing API calls."""
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    if not supplied or not expected or supplied != expected:
        raise HTTPException(status_code=403, detail="csrf_failed")


def require_api_user(request: Request, db: Session) -> dict[str, Any]:
    session = current_session(request, db)
    if session is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return session
