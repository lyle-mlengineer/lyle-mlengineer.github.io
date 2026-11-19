from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..deps import get_db, require_api_user, require_csrf
from ..rag.ingest import sync_portfolio

router = APIRouter(tags=["portfolio"])


@router.post("/api/portfolio/reindex")
def reindex(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    """Re-sync the Markdown corpus. Unchanged files are skipped by hash."""
    session = require_api_user(request, db)
    require_csrf(request, session)

    report = sync_portfolio(db, get_settings())
    return {
        "docs_indexed": report.docs_indexed,
        "docs_skipped": report.docs_skipped,
        "docs_removed": report.docs_removed,
        "chunks": report.chunks_written,
        "changed": report.changed,
    }
