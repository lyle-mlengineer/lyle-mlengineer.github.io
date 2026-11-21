import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import (
    auth,
    compose,
    copy,
    documents,
    health,
    qa,
    render,
    runs,
    search,
    sites,
    video,
)
from app.config import get_settings
from app.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("snaptospot")


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.database_url.startswith("sqlite"):
            init_db()
        yield

    app = FastAPI(
        title="SnapToSpot",
        version=__version__,
        summary="Turn a website into a native campaign kit for every social platform.",
        debug=settings.debug,
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sites.router)
    app.include_router(runs.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(compose.router)
    app.include_router(render.router)
    app.include_router(video.router)
    app.include_router(copy.router)
    app.include_router(qa.router)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/healthz",
        }

    logger.info("SnapToSpot %s started in %s mode", __version__, settings.env)
    return app


app = create_app()
