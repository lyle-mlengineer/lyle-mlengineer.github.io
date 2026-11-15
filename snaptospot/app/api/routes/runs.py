from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import FactRecord, Run
from app.pipeline.resolve.service import (
    ConflictError,
    NotFoundError,
    ResolveError,
    apply_answers,
    apply_fact_action,
    build_gap_report,
    ensure_facts,
    render_report,
)
from app.schemas.resolve import (
    AnswersIn,
    FactActionIn,
    FactOut,
    GapReport,
    RenderOut,
)
from app.schemas.run import RunOut, run_to_out

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def _run_or_404(run_id: str, user: CurrentUser, db: DbSession) -> Run:
    run = db.scalar(select(Run).where(Run.id == run_id, Run.tenant_id == user.tenant_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: CurrentUser, db: DbSession) -> RunOut:
    return run_to_out(_run_or_404(run_id, user, db))


@router.get("", response_model=list[RunOut])
def list_runs(user: CurrentUser, db: DbSession, site_id: str | None = None) -> list[RunOut]:
    query = select(Run).where(Run.tenant_id == user.tenant_id)
    if site_id:
        query = query.where(Run.site_id == site_id)
    runs = db.scalars(query.order_by(Run.created_at.desc()).limit(50))
    return [run_to_out(run) for run in runs]


@router.get("/{run_id}/gaps", response_model=GapReport)
def get_gaps(run_id: str, user: CurrentUser, db: DbSession) -> GapReport:
    run = _run_or_404(run_id, user, db)
    try:
        report = build_gap_report(db, run)
    except ResolveError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return report


@router.get("/{run_id}/facts", response_model=list[FactOut])
def list_facts(
    run_id: str,
    user: CurrentUser,
    db: DbSession,
    status: str | None = None,
) -> list[FactOut]:
    run = _run_or_404(run_id, user, db)
    ensure_facts(db, run)
    db.commit()
    query = select(FactRecord).where(
        FactRecord.run_id == run.id, FactRecord.tenant_id == run.tenant_id
    )
    if status:
        query = query.where(FactRecord.status == status)
    facts = db.scalars(query.order_by(FactRecord.tier, FactRecord.key, FactRecord.id))
    return [FactOut.model_validate(fact) for fact in facts]


@router.post("/{run_id}/answers", response_model=GapReport)
def answer_gaps(
    run_id: str,
    body: AnswersIn,
    user: CurrentUser,
    db: DbSession,
) -> GapReport:
    run = _run_or_404(run_id, user, db)
    try:
        report = apply_answers(db, run, user.id, body.answers)
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResolveError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return report


@router.post("/{run_id}/facts/{fact_id}", response_model=FactOut)
def act_on_fact(
    run_id: str,
    fact_id: str,
    body: FactActionIn,
    user: CurrentUser,
    db: DbSession,
) -> FactOut:
    run = _run_or_404(run_id, user, db)
    try:
        fact = apply_fact_action(db, run, user.id, fact_id, body)
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResolveError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return FactOut.model_validate(fact)


@router.post("/{run_id}/render", response_model=RenderOut)
def render(run_id: str, user: CurrentUser, db: DbSession) -> JSONResponse:
    run = _run_or_404(run_id, user, db)
    try:
        report = render_report(db, run)
    except ResolveError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    status_code = 202 if report.ready else 409
    return JSONResponse(
        status_code=status_code,
        content=report.model_dump(mode="json", by_alias=True),
    )
