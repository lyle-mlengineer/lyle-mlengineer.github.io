from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Run
from app.qa.service import QaError, run_qa
from app.schemas.qa import QaIn, QaOut

router = APIRouter(prefix="/v1/runs", tags=["qa"])


@router.post("/{run_id}/qa", response_model=QaOut)
def qa(
    run_id: str,
    body: QaIn,
    user: CurrentUser,
    db: DbSession,
) -> QaOut:
    """Run every gate on the composed kit and write ``qa.json``."""
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        report = run_qa(db, run, body)
    except QaError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return report
