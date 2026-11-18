from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Run
from app.render.encode import EncodeError
from app.render.service import ComposeFirstError
from app.render.video import VideoError, render_run_videos
from app.schemas.video import VideoIn, VideoOut

router = APIRouter(prefix="/v1/runs", tags=["video"])


@router.post("/{run_id}/videos", response_model=VideoOut)
def video(
    run_id: str,
    body: VideoIn,
    user: CurrentUser,
    db: DbSession,
) -> VideoOut:
    """Render deterministic MP4s and poster frames for a composed run."""
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        report = render_run_videos(db, run, body, user.id)
    except ComposeFirstError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VideoError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EncodeError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    db.commit()
    return report
