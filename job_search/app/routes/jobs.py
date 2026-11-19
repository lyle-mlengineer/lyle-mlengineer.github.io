"""Job intake, run polling and cancellation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import utcnow
from ..deps import get_db, require_api_user, require_csrf
from ..documents.storage import artifact_file, download_name
from ..jobs.ingest import DuplicateJob, IngestError, ingest
from ..jobs.pipeline import RunError, create_run, execute_run
from ..models import Artifact, Job, Run, RunStep
from ..providers.fetch.http import Fetcher
from ..skills.registry import SKILL_REGISTRY, get_skill

router = APIRouter(tags=["jobs"])


def _error(http_status: int, code: str, message: str, **details: Any) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=http_status)


@router.post("/api/jobs", status_code=202)
def create_job(
    request: Request,
    background: BackgroundTasks,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    return _create(request, background, db, payload=body, attach=False)


@router.post("/api/jobs/{job_id}/runs", status_code=202)
def retry_job(
    job_id: int,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    latest = db.scalar(select(Run).where(Run.job_id == job.id).order_by(Run.created_at.desc()).limit(1))
    if latest is not None and latest.status in {"queued", "running"}:
        return _error(409, "conflict", "A run is already in flight for this job.", job_id=job.id)
    try:
        run = create_run(db, job, seed_prior=True)
    except RunError as exc:
        return _error(409, "conflict", str(exc), job_id=job.id)
    db.commit()
    _schedule(request, background, run.id)
    return JSONResponse(
        {"job_id": job.id, "run_id": run.id, "poll_url": f"/api/runs/{run.id}"},
        status_code=202,
    )


@router.post("/api/jobs/{job_id}/regenerate", status_code=202)
def regenerate(
    job_id: int,
    request: Request,
    background: BackgroundTasks,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    skill_name = str((body or {}).get("skill") or "").strip()
    if skill_name not in SKILL_REGISTRY:
        return _error(422, "validation_error", "Unknown skill.", skills=sorted(SKILL_REGISTRY))
    if skill_name not in {"job_summary", "cv_writing"}:
        return _error(422, "validation_error", "That skill cannot be regenerated yet.", skill=skill_name)
    if "job_extraction" in get_skill(skill_name).requires and not job.extract_json:
        return _error(409, "conflict", "Finish the first run before regenerating this artifact.")

    try:
        run = create_run(db, job, skills=(skill_name,), kind="regenerate")
    except RunError as exc:
        return _error(409, "conflict", str(exc), job_id=job.id)
    db.commit()
    _schedule(request, background, run.id)
    return JSONResponse(
        {
            "job_id": job.id,
            "run_id": run.id,
            "poll_url": f"/api/runs/{run.id}",
            "skill": skill_name,
        },
        status_code=202,
    )


@router.get("/api/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: int, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    require_api_user(request, db)
    artifact = db.get(Artifact, artifact_id)
    path = artifact_file(artifact, get_settings()) if artifact else None
    if artifact is None or path is None:
        raise HTTPException(status_code=404, detail="not_found")
    return FileResponse(
        path,
        media_type=_media_type(artifact.format),
        filename=download_name(artifact),
        content_disposition_type="attachment",
    )


@router.get("/api/artifacts/{artifact_id}/preview")
def preview_artifact(artifact_id: int, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    require_api_user(request, db)
    artifact = db.get(Artifact, artifact_id)
    path = artifact_file(artifact, get_settings()) if artifact else None
    if artifact is None or path is None:
        raise HTTPException(status_code=404, detail="not_found")
    return FileResponse(
        path,
        media_type=_media_type(artifact.format),
        filename=download_name(artifact),
        content_disposition_type="inline",
    )


def _media_type(fmt: str) -> str:
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "md": "text/markdown; charset=utf-8",
    }.get(fmt, "application/octet-stream")


def _create(
    request: Request,
    background: BackgroundTasks,
    db: Session,
    *,
    payload: dict[str, Any] | None,
    attach: bool,
) -> JSONResponse:
    settings = get_settings()
    llm = getattr(request.app.state, "llm", None)
    if llm is None:
        return _error(503, "provider_error", "The LLM provider is not configured.")

    if not isinstance(payload, dict):
        return _error(422, "validation_error", "Expected a JSON object with a link or posting text.")

    fetcher = getattr(request.app.state, "fetcher", None)
    if fetcher is None:
        fetcher = Fetcher(
            max_bytes=settings.fetch_max_bytes,
            timeout_s=settings.fetch_timeout_s,
            max_redirects=settings.fetch_max_redirects,
        )

    try:
        result = ingest(
            db,
            settings,
            source_url=payload.get("source_url"),
            source_text=payload.get("source_text"),
            fetcher=fetcher,
            attach=attach or _truthy(request.query_params.get("attach")),
        )
    except DuplicateJob as exc:
        return _error(
            409,
            "duplicate_job",
            "That job is already tracked.",
            job_id=exc.job.id,
            job_url=f"/jobs/{exc.job.id}",
            attach_url="/api/jobs?attach=1",
        )
    except IngestError as exc:
        status = 409 if exc.code == "conflict" else 422
        return _error(status, exc.code, str(exc))

    db.commit()
    _schedule(request, background, result.run_id)
    return JSONResponse(
        {
            "job_id": result.job.id,
            "run_id": result.run_id,
            "poll_url": f"/api/runs/{result.run_id}",
            "job_url": f"/jobs/{result.job.id}",
            "attached": result.attached,
            "warning": result.warning,
        },
        status_code=202,
    )


@router.get("/api/runs/{run_id}")
def get_run(run_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_api_user(request, db)
    run = db.scalar(select(Run).options(selectinload(Run.steps)).where(Run.id == run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="not_found")
    job = db.get(Job, run.job_id)
    return JSONResponse(
        {
            "id": run.id,
            "job_id": run.job_id,
            "status": run.status,
            "progress_pct": run.progress_pct,
            "current_step": run.current_step,
            "completed_steps": run.completed_steps,
            "total_steps": run.total_steps,
            "error": run.error,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "tokens_in": run.tokens_in,
            "tokens_out": run.tokens_out,
            "cost_usd": run.cost_usd,
            "job_status": job.status if job else None,
            "steps": [
                {
                    "skill": step.skill,
                    "status": step.status,
                    "duration_ms": step.duration_ms,
                    "tokens_in": step.tokens_in,
                    "tokens_out": step.tokens_out,
                    "error": step.error,
                }
                for step in run.steps
            ],
        }
    )


@router.post("/api/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="not_found")
    if run.status in {"succeeded", "failed", "cancelled", "interrupted"}:
        return _error(409, "conflict", "That run has already finished.", run_status=run.status)

    run.cancel_requested = True
    if run.status == "queued":
        run.status = "cancelled"
        run.error = "Cancelled before it started."
        run.finished_at = utcnow()
        db.execute(
            update(RunStep)
            .where(RunStep.run_id == run.id, RunStep.status == "pending")
            .values(status="skipped", finished_at=utcnow())
        )
    db.commit()
    return JSONResponse({"run_id": run.id, "status": run.status}, status_code=202)


def _schedule(request: Request, background: BackgroundTasks, run_id: int) -> None:
    settings = get_settings()
    llm = request.app.state.llm
    background.add_task(execute_run, run_id, settings, llm)


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}
