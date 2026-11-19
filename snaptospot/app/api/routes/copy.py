from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.copy.deck import CopyValidationError
from app.copy.service import CopyError, CopyFirstError, copy_run
from app.models import Run
from app.schemas.copy import CopyIn, CopyOut

router = APIRouter(prefix="/v1/runs", tags=["copy"])


@router.post("/{run_id}/copy", response_model=CopyOut)
def copy(
    run_id: str,
    body: CopyIn,
    user: CurrentUser,
    db: DbSession,
) -> CopyOut:
    """Generate validated, platform-native copy decks for a run."""
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        report = copy_run(db, run, body, user.id)
    except CopyFirstError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CopyValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CopyError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return report
