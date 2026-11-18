from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.compose.service import ComposeError
from app.models import Run
from app.render.service import ComposeFirstError, RenderError, render_run
from app.schemas.render import RenderIn, RenderOut

router = APIRouter(prefix="/v1/runs", tags=["render"])


@router.post("/{run_id}/stills", response_model=RenderOut)
def render(
    run_id: str,
    body: RenderIn,
    user: CurrentUser,
    db: DbSession,
) -> RenderOut:
    """Render the run's measured cards to deterministic PNG stills."""
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        report = render_run(db, run, body, user.id)
    except ComposeError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ComposeFirstError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RenderError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return report
