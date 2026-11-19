"""FastAPI application factory.

Boot order matters: settings → directories → schema → account → sweeps → routes.
Anything that can fail (missing keys, unseeded account) must fail here or be
visible on ``/readyz`` — never as a stack trace in a page.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, get_settings
from .db import get_session_factory, init_db, session_scope, sweep_expired_sessions, sweep_interrupted_runs
from .domain import ARTIFACT_LABELS, JOB_STATUS_LABELS, JOB_STATUSES, SKILL_LABELS, STATUS_TONE
from .providers.llm.base import LLMProviderError
from .providers.llm.registry import build_llm_provider
from .providers.search.registry import build_search_provider
from .rag.ingest import reindex
from .routes import API_ROUTERS, PAGE_ROUTER
from .security import seed_admin

logger = logging.getLogger("skipper")

TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_runtime_dirs()
    init_db(settings)
    app.state.secret_key = settings.resolve_secret_key()

    with session_scope(settings) as session:
        seed_admin(session, settings)

    expired = sweep_expired_sessions(settings)
    interrupted = sweep_interrupted_runs(settings)
    if expired or interrupted:
        logger.info("startup sweep: %s sessions, %s runs", expired, interrupted)

    factory = get_session_factory(settings)
    app.state.session_factory = factory
    try:
        app.state.llm = build_llm_provider(settings, session_factory=factory)
    except LLMProviderError as exc:
        logger.warning("LLM provider unavailable: %s", exc)
        app.state.llm = None
    app.state.search = build_search_provider(settings, session_factory=factory)

    try:
        report = reindex(settings)
        if report.changed:
            logger.info(
                "portfolio index: %s docs, %s chunks (%s removed)",
                report.docs_indexed,
                report.chunks_written,
                report.docs_removed,
            )
    except Exception:
        logger.exception("portfolio indexing failed; the corpus is unchanged")

    logger.info(
        "Skipper ready (env=%s, llm=%s, search=%s)",
        settings.env,
        settings.llm_provider,
        settings.search_provider,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title="Skipper",
        description="A private job-search agent: one posting in, a complete application pack out.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if not settings.is_prod else None,
        redoc_url=None,
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.globals.update(
        app_name="Skipper",
        owner="Lyle Okoth",
        year=time.gmtime().tm_year,
        portfolio_url="https://lyle-mlengineer.github.io/",
        settings=settings,
        status_labels=JOB_STATUS_LABELS,
        status_tone=STATUS_TONE,
        status_order=JOB_STATUSES,
        artifact_labels=ARTIFACT_LABELS,
        skill_labels=SKILL_LABELS,
    )
    app.state.templates = templates

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
            return JSONResponse(
                {"error": {"code": "internal", "message": "Something went wrong.", "request_id": request_id}},
                status_code=500,
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unicons.iconscout.com; "
            "font-src 'self' https://fonts.gstatic.com https://unicons.iconscout.com data:; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        if duration_ms > 500:
            logger.warning("slow request %s %s %sms", request.method, request.url.path, duration_ms)
        return response

    app.include_router(PAGE_ROUTER)
    for router in API_ROUTERS:
        app.include_router(router)

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                {"error": {"code": "not_found", "message": "No such endpoint."}}, status_code=404
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {"status": 404, "message": "That page does not exist."},
            status_code=404,
        )

    return app


app = create_app()
