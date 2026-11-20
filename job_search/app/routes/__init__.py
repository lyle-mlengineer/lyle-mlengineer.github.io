"""Route registration."""

from __future__ import annotations

from .audio import router as audio_router
from .auth import router as auth_router
from .health import router as health_router
from .interview import router as interview_router
from .jobs import router as jobs_router
from .pages import router as PAGE_ROUTER
from .portfolio import router as portfolio_router

API_ROUTERS = [auth_router, health_router, portfolio_router, audio_router, jobs_router, interview_router]

__all__ = ["API_ROUTERS", "PAGE_ROUTER"]
