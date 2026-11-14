import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.auth.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.config import get_settings
from app.models import AuditLog, RefreshToken, Tenant, User
from app.models.base import ensure_aware, utcnow
from app.schemas.auth import LogoutRequest, RefreshRequest, SignupRequest, TokenPair

router = APIRouter(prefix="/v1", tags=["auth"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "workspace"


def _issue_tokens(db: Session, user: User) -> TokenPair:
    settings = get_settings()
    access = create_access_token(user.id, user.tenant_id)
    raw_refresh = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/auth/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: DbSession) -> TokenPair:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    tenant = Tenant(
        name=body.tenant_name or f"{email.split('@')[0]}'s workspace",
        slug=f"{_slugify(body.tenant_name or email.split('@')[0])}-{new_refresh_token()[:6]}",
    )
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_user_id=user.id,
            action="auth.signup",
            target_type="user",
            target_id=user.id,
        )
    )
    pair = _issue_tokens(db, user)
    db.commit()
    return pair


@router.post("/token", response_model=TokenPair)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(user.password_hash, form.password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    pair = _issue_tokens(db, user)
    db.commit()
    return pair


@router.post("/token/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: DbSession) -> TokenPair:
    token_hash = hash_refresh_token(body.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None or row.revoked_at is not None or ensure_aware(row.expires_at) < utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    row.revoked_at = utcnow()
    pair = _issue_tokens(db, user)
    db.commit()
    return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, db: DbSession) -> Response:
    token_hash = hash_refresh_token(body.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is not None and row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser, db: DbSession) -> dict[str, object]:
    tenant = db.get(Tenant, user.tenant_id)
    return {
        "user_id": user.id,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "tenant_name": tenant.name if tenant else None,
        "plan": tenant.plan if tenant else None,
    }
