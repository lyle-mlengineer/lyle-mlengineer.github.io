"""HTML pages. These render; the JSON API under ``/api`` mutates."""

from __future__ import annotations

import secrets
import shutil
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..config import get_settings
from ..db import utcnow
from ..deps import current_session, get_db
from ..domain import ACTIVE_JOB_STATUSES, JOB_STATUS_LABELS, JOB_STATUSES
from ..jobs.render import markdown_to_html
from ..models import Company, Job, PortfolioChunk, PortfolioDoc, Run, User
from ..rag.ingest import sync_portfolio
from ..security import (
    clear_login_failures,
    create_session,
    hash_ip,
    is_login_throttled,
    record_login_failure,
    revoke_session,
    verify_password,
)

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


def safe_next(value: str | None) -> str:
    """Only allow local, absolute-path redirects."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/dashboard"
    return value


def _login_context(request: Request, error: str | None = None, username: str = "") -> dict[str, Any]:
    return {
        "error": error,
        "username": username,
        "next": safe_next(request.query_params.get("next")),
    }


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    """Public portfolio-style landing page. No database, no session required."""
    return _templates(request).TemplateResponse(
        request,
        "landing.html",
        {"page": "home"},
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    next: str | None = None,
) -> Response:
    if current_session(request, db) is not None:
        return RedirectResponse(safe_next(next), status_code=303)
    return _templates(request).TemplateResponse(
        request, "login.html", _login_context(request)
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(default=None),
) -> Response:
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"
    ip_digest = hash_ip(ip, settings.resolve_secret_key())
    username_clean = username.strip()[:64]
    target = safe_next(next or request.query_params.get("next"))

    if is_login_throttled(db, ip_digest, username_clean):
        db.commit()
        return _templates(request).TemplateResponse(
            request,
            "login.html",
            {**_login_context(request), "username": username_clean,
             "error": "Too many attempts. Try again in 15 minutes."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = db.execute(select(User).where(User.username == username_clean)).scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, password):
        record_login_failure(db, ip_digest, username_clean)
        db.commit()
        return _templates(request).TemplateResponse(
            request,
            "login.html",
            {**_login_context(request), "username": username_clean,
             "error": "That username and password do not match."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    clear_login_failures(db, ip_digest, username_clean)
    token, _csrf = create_session(
        db,
        settings,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_hash=ip_digest,
    )
    db.commit()
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
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


@router.post("/logout")
def logout_form(request: Request, db: Session = Depends(get_db)) -> Response:
    revoke_session(db, request.cookies.get(get_settings().session_cookie))
    db.commit()
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(get_settings().session_cookie, path="/")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> Response:
    session = current_session(request, db)
    if session is None:
        return RedirectResponse("/login?next=/dashboard", status_code=303)

    counts = dict(
        db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    )
    pending_action = db.execute(
        select(Job)
        .options(joinedload(Job.company))
        .where(Job.status.in_(ACTIVE_JOB_STATUSES), Job.next_action.is_not(None))
        .order_by(Job.next_action_at.asc())
        .limit(5)
    ).scalars().all()
    recent = db.execute(
        select(Job).options(joinedload(Job.company)).order_by(Job.updated_at.desc()).limit(5)
    ).scalars().all()
    company_count = db.execute(select(func.count(Company.id))).scalar_one()
    settings = get_settings()
    portfolio_chunks = db.execute(select(func.count(PortfolioChunk.id))).scalar_one()

    return _templates(request).TemplateResponse(
        request,
        "dashboard.html",
        {
            "page": "dashboard",
            "session": session,
            "csrf_token": session["csrf_token"],
            "counts": counts,
            "status_labels": JOB_STATUS_LABELS,
            "total_jobs": sum(counts.values()),
            "active_jobs": sum(counts.get(s, 0) for s in ACTIVE_JOB_STATUSES),
            "company_count": company_count,
            "pending_action": pending_action,
            "recent": recent,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model_small if settings.llm_provider != "fake" else "fake (offline)",
            "search_provider": settings.search_provider,
            "pdf_engine": "libreoffice" if shutil.which(settings.soffice_path) else "reportlab",
            "portfolio_chunks": portfolio_chunks,
        },
    )


@router.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request, db: Session = Depends(get_db)) -> Response:
    session = current_session(request, db)
    if session is None:
        return RedirectResponse("/login?next=/jobs", status_code=303)

    status_filter = request.query_params.get("status", "").strip()
    query = request.query_params.get("q", "").strip()[:120]
    stmt = select(Job).options(joinedload(Job.company), selectinload(Job.runs)).order_by(Job.updated_at.desc())
    if status_filter in JOB_STATUSES:
        stmt = stmt.where(Job.status == status_filter)
    if query:
        stmt = stmt.outerjoin(Company, Job.company_id == Company.id).where(
            or_(Job.title.ilike(f"%{query}%"), Company.name.ilike(f"%{query}%"))
        )
    jobs = db.execute(stmt.limit(100)).unique().scalars().all()

    return _templates(request).TemplateResponse(
        request,
        "jobs.html",
        {
            "page": "jobs",
            "session": session,
            "csrf_token": session["csrf_token"],
            "jobs": jobs,
            "status_labels": JOB_STATUS_LABELS,
            "status_filter": status_filter,
            "query": query,
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, db: Session = Depends(get_db)) -> Response:
    session = current_session(request, db)
    if session is None:
        return RedirectResponse(f"/login?next=/jobs/{job_id}", status_code=303)

    job = db.scalar(
        select(Job)
        .options(
            joinedload(Job.company),
            selectinload(Job.runs).selectinload(Run.steps),
            selectinload(Job.artifacts),
            selectinload(Job.events),
        )
        .where(Job.id == job_id)
    )
    if job is None:
        return _templates(request).TemplateResponse(
            request,
            "error.html",
            {"status": 404, "message": "That job does not exist."},
            status_code=404,
        )

    latest_run = job.runs[0] if job.runs else None
    summary = next(
        (artifact for artifact in job.artifacts if artifact.kind == "job_summary" and artifact.is_current),
        None,
    )
    return _templates(request).TemplateResponse(
        request,
        "job_detail.html",
        {
            "page": "jobs",
            "session": session,
            "csrf_token": session["csrf_token"],
            "job": job,
            "latest_run": latest_run,
            "summary_html": markdown_to_html(summary.content_md) if summary and summary.content_md else None,
            "events": job.events[:8],
        },
    )


@router.get("/companies", response_class=HTMLResponse)
def companies_page(request: Request, db: Session = Depends(get_db)) -> Response:
    session = current_session(request, db)
    if session is None:
        return RedirectResponse("/login?next=/companies", status_code=303)
    companies = db.execute(
        select(Company).options(selectinload(Company.jobs)).order_by(Company.name.asc())
    ).scalars().all()
    return _templates(request).TemplateResponse(
        request,
        "companies.html",
        {
            "page": "companies",
            "session": session,
            "csrf_token": session["csrf_token"],
            "companies": companies,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)) -> Response:
    session = current_session(request, db)
    if session is None:
        return RedirectResponse("/login?next=/settings", status_code=303)
    settings = get_settings()
    return _templates(request).TemplateResponse(
        request,
        "settings.html",
        {
            "page": "settings",
            "session": session,
            "csrf_token": session["csrf_token"],
            "settings": settings,
            "now": utcnow(),
            "portfolio_docs": db.execute(select(func.count(PortfolioDoc.id))).scalar_one(),
            "portfolio_chunks": db.execute(select(func.count(PortfolioChunk.id))).scalar_one(),
            "reindex_notice": request.query_params.get("indexed"),
            "reindex_chunks": request.query_params.get("chunks"),
            "reindex_removed": request.query_params.get("removed"),
        },
    )


@router.post("/settings/reindex")
def reindex_portfolio(
    request: Request,
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
) -> Response:
    session = current_session(request, db)
    if session is None:
        return RedirectResponse("/login?next=/settings", status_code=303)
    if not secrets.compare_digest(csrf_token, session.get("csrf_token", "")):
        raise HTTPException(status_code=403, detail="csrf_failed")

    report = sync_portfolio(db, get_settings())
    params = (
        f"indexed={report.docs_indexed}&chunks={report.chunks_written}"
        f"&removed={report.docs_removed}"
    )
    return RedirectResponse(f"/settings?{params}", status_code=303)
