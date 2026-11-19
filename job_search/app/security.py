"""Authentication primitives: argon2id passwords, opaque sessions, CSRF, throttling.

The app has exactly one user. Sessions are rows so sign-out is immediate and
expiry is enforceable without JWT machinery.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import AuthSession, LoginAttempt, User, utcnow

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_MINUTES = 15


# ---------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# ---------------------------------------------------------------- sessions


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(ip: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _expiry(settings: Settings) -> str:
    value = datetime.now(UTC) + timedelta(hours=settings.session_hours)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_session(
    db: Session,
    settings: Settings,
    user: User,
    *,
    user_agent: str | None = None,
    ip_hash: str | None = None,
) -> tuple[str, str]:
    """Create a session row and return ``(cookie_token, csrf_token)``."""
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    now = utcnow()
    db.add(
        AuthSession(
            id=hash_token(token),
            user_id=user.id,
            csrf_token=csrf_token,
            created_at=now,
            expires_at=_expiry(settings),
            last_seen_at=now,
            user_agent=(user_agent or "")[:255] or None,
            ip_hash=ip_hash,
        )
    )
    user.last_login_at = now
    db.flush()
    return token, csrf_token


def load_session(db: Session, token: str | None) -> dict[str, Any] | None:
    """Return the session+user for a cookie token, or ``None``.

    Expired sessions are deleted on sight. ``last_seen_at`` rolls forward at most
    once a minute so a read does not become a write on every request.
    """
    if not token:
        return None
    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.id == hash_token(token))
    ).first()
    if row is None:
        return None
    session, user = row
    if session.expires_at <= utcnow() or not user.is_active:
        db.delete(session)
        db.flush()
        return None
    now = datetime.now(UTC)
    last_seen = datetime.fromisoformat(session.last_seen_at.replace("Z", "+00:00"))
    if now - last_seen > timedelta(minutes=1):
        session.last_seen_at = utcnow()
    return {
        "session_id": session.id,
        "csrf_token": session.csrf_token,
        "expires_at": session.expires_at,
        "user_id": user.id,
        "username": user.username,
    }


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    db.execute(delete(AuthSession).where(AuthSession.id == hash_token(token)))


# ---------------------------------------------------------------- throttling


def is_login_throttled(db: Session, ip_hash: str, username: str) -> bool:
    since = (datetime.now(UTC) - timedelta(minutes=LOGIN_WINDOW_MINUTES)).replace(microsecond=0) \
        .isoformat().replace("+00:00", "Z")
    count = db.execute(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.ip_hash == ip_hash,
            LoginAttempt.username == username.lower(),
            LoginAttempt.attempted_at >= since,
        )
    ).scalar_one()
    return count >= LOGIN_MAX_FAILURES


def record_login_failure(db: Session, ip_hash: str, username: str) -> None:
    db.add(LoginAttempt(ip_hash=ip_hash, username=username.lower(), attempted_at=utcnow()))
    cutoff = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0) \
        .isoformat().replace("+00:00", "Z")
    db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
    db.flush()


def clear_login_failures(db: Session, ip_hash: str, username: str) -> None:
    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.ip_hash == ip_hash, LoginAttempt.username == username.lower()
        )
    )


# ---------------------------------------------------------------- seeding


def seed_admin(db: Session, settings: Settings) -> None:
    """Create the single account on first boot.

    Development gets a documented default so the app runs from a fresh clone.
    Production refuses to seed without an explicit password; ``/readyz`` reports it.
    """
    users = db.execute(select(func.count(User.id))).scalar_one()
    if users:
        return
    password = settings.admin_password
    if not password and not settings.is_prod:
        password = "skipper-dev"
        print(
            "[skipper] WARNING: SKIPPER_ADMIN_PASSWORD is unset; seeded the development "
            f"account '{settings.admin_user}' with password 'skipper-dev'.",
            flush=True,
        )
    if not password:
        print("[skipper] ERROR: no account exists and SKIPPER_ADMIN_PASSWORD is unset.", flush=True)
        return
    db.add(
        User(
            username=settings.admin_user,
            password_hash=hash_password(password),
            created_at=utcnow(),
        )
    )
    db.flush()
    print(f"[skipper] Seeded the account '{settings.admin_user}'.", flush=True)


def user_count(db: Session) -> int:
    return int(db.execute(select(func.count(User.id))).scalar_one())
