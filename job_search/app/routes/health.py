"""Liveness and readiness.

``/healthz`` must not touch the database: it answers "is the process up?".
``/readyz`` answers "can this instance serve the app?" and names what is missing.
"""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import get_db
from ..models import PortfolioChunk
from ..security import user_count

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(response: Response, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    components: dict[str, object] = {}

    try:
        db.execute(text("SELECT 1"))
        components["database"] = True
    except Exception as exc:  # pragma: no cover - only on a broken volume
        components["database"] = f"error: {exc}"

    try:
        components["account"] = user_count(db) > 0
    except Exception:
        components["account"] = False

    components["llm"] = (
        settings.llm_provider == "fake" or bool(settings.groq_api_key)
    )
    components["search"] = (
        settings.search_provider == "duckduckgo" or bool(settings.serper_api_key)
        or settings.search_provider == "auto"
    )
    try:
        components["portfolio_chunks"] = int(
            db.execute(select(func.count(PortfolioChunk.id))).scalar_one()
        )
    except Exception:
        components["portfolio_chunks"] = 0
    components["pdf_engine"] = (
        "libreoffice" if shutil.which(settings.soffice_path) else "reportlab"
    )

    ready = bool(components["database"]) and bool(components["account"])
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "components": components}
