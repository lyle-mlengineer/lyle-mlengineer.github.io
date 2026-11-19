"""JSON auth endpoints used by the login page and future app pages.

The HTML form posts to ``/login``; these endpoints exist so the app can do the
same thing without a page reload, and so session/CSRF behaviour is testable.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import current_session, get_db, require_api_user, require_csrf
from ..models import User
from ..security import (
    clear_login_failures,
    create_session,
    hash_ip,
    is_login_throttled,
    record_login_failure,
    revoke_session,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return True  # non-browser client; CSRF is a browser problem
    host = request.headers.get("host", "")
    return urlparse(origin).netloc == host


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def api_login(
    payload: LoginPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()
    if not _same_origin(request):
        raise HTTPException(status_code=403, detail="csrf_failed")

    ip = request.client.host if request.client else "unknown"
    ip_digest = hash_ip(ip, settings.resolve_secret_key())
    username = payload.username.strip()

    if is_login_throttled(db, ip_digest, username):
        db.commit()
        raise HTTPException(status_code=429, detail="rate_limited")

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, payload.password):
        record_login_failure(db, ip_digest, username)
        db.commit()
        raise HTTPException(status_code=401, detail="invalid_credentials")

    clear_login_failures(db, ip_digest, username)
    token, _csrf = create_session(
        db,
        settings,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_hash=ip_digest,
    )
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.is_prod,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def api_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    session = current_session(request, db)
    if session is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    require_csrf(request, session)
    revoke_session(db, request.cookies.get(get_settings().session_cookie))
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(get_settings().session_cookie, path="/")
    return response


@router.get("/me")
def api_me(request: Request, db: Session = Depends(get_db)) -> dict:
    session = require_api_user(request, db)
    return {
        "username": session["username"],
        "csrf_token": session["csrf_token"],
        "expires_at": session["expires_at"],
    }
