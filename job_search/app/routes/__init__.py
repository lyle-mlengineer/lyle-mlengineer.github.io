"""Route registration."""

from __future__ import annotations

from .auth import router as auth_router
from .health import router as health_router
from .pages import router as PAGE_ROUTER

API_ROUTERS = [auth_router, health_router]

__all__ = ["API_ROUTERS", "PAGE_ROUTER"]
