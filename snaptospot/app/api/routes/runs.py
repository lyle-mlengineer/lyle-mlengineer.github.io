from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Run
from app.schemas.run import RunOut, run_to_out

router = APIRouter(prefix="/v1/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: CurrentUser, db: DbSession) -> RunOut:
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_to_out(run)


@router.get("", response_model=list[RunOut])
def list_runs(user: CurrentUser, db: DbSession, site_id: str | None = None) -> list[RunOut]:
    query = select(Run).where(Run.tenant_id == user.tenant_id)
    if site_id:
        query = query.where(Run.site_id == site_id)
    runs = db.scalars(query.order_by(Run.created_at.desc()).limit(50))
    return [run_to_out(run) for run in runs]
