from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.compose.service import ComposeError, UnknownPlatformError, compose_run
from app.models import Run
from app.schemas.design import ComposeIn, ComposeOut

router = APIRouter(prefix="/v1/runs", tags=["compose"])


@router.post("/{run_id}/compose", response_model=ComposeOut)
def compose(
    run_id: str,
    body: ComposeIn,
    user: CurrentUser,
    db: DbSession,
) -> ComposeOut:
    """Turn the accepted facts into measured, fact-linked cards."""
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        report = compose_run(db, run, body, user.id)
    except UnknownPlatformError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ComposeError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return report
