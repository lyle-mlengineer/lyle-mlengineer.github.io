from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Run
from app.pipeline.resolve.web import run_web_search
from app.schemas.search import SearchOut

router = APIRouter(prefix="/v1/runs", tags=["search"])


@router.post("/{run_id}/search", response_model=SearchOut)
def search_run(run_id: str, user: CurrentUser, db: DbSession) -> SearchOut:
    """Fill public, professional gaps from scored, dated web sources."""
    run = db.scalar(
        select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        report = run_web_search(db, run, user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return report
