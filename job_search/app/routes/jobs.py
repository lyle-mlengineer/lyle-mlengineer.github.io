"""Job intake, run polling and cancellation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import utcnow
from ..deps import get_db, require_api_user, require_csrf
from ..documents.storage import artifact_file, download_name
from ..jobs.discover import default_roles, discover, looks_like_listing
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


@router.post("/api/jobs/discover")
def discover_jobs(
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    payload = body or {}
    source_url = str(payload.get("source_url") or "").strip()
    if not source_url:
        return _error(422, "validation_error", "Paste a company or careers page link first.")
    fetcher = getattr(request.app.state, "fetcher", None)
    if fetcher is None:
        fetcher = _fetcher(get_settings())
    roles = _roles(payload, get_settings())
    try:
        found = discover(
            source_url=source_url,
            roles=roles,
            fetcher=fetcher,
            search=getattr(request.app.state, "search", None),
            settings=get_settings(),
        )
    except ValueError as exc:
        return _error(422, "validation_error", str(exc))
    return JSONResponse(_discovery_body(found, roles))


@router.post("/api/jobs/bulk", status_code=202)
def create_jobs_bulk(
    request: Request,
    background: BackgroundTasks,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    settings = get_settings()
    fetcher = getattr(request.app.state, "fetcher", None) or _fetcher(settings)
    items = (body or {}).get("items")
    if not isinstance(items, list) or not items:
        return _error(422, "validation_error", "Select at least one job to add.")
    if len(items) > 30:
        return _error(422, "validation_error", "Add at most 30 jobs at once.")

    added: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for item in items:
        url = str((item or {}).get("url") if isinstance(item, dict) else item).strip()
        if not url:
            continue
        try:
            with db.begin_nested():
                result = ingest(
                    db, settings, source_url=url, source_text=None, fetcher=fetcher, attach=False
                )
            added.append(
                {
                    "job_id": result.job.id,
                    "run_id": result.run_id,
                    "job_url": f"/jobs/{result.job.id}",
                    "title": result.job.title,
                }
            )
        except DuplicateJob as exc:
            skipped.append({"url": url, "reason": "already tracked", "job_url": f"/jobs/{exc.job.id}"})
        except IngestError as exc:
            skipped.append({"url": url, "reason": str(exc)})
    db.commit()
    for row in added:
        _schedule(request, background, row["run_id"])
    return JSONResponse(
        {"added": added, "skipped": skipped, "count": len(added)},
        status_code=202,
    )


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
    if skill_name == "job_extraction":
        return _error(422, "validation_error", "Extraction is regenerated by re-running the whole pipeline.")
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
    if artifact is None:
        raise HTTPException(status_code=404, detail="not_found")
    path = artifact_file(artifact, get_settings())
    if path is None and artifact.content_md:
        filename = f"skipper-{artifact.kind}-v{artifact.version}.md"
        return Response(
            artifact.content_md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if path is None:
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

    source_url = str(payload.get("source_url") or "").strip()
    if (
        source_url
        and not attach
        and payload.get("discover") is not False
        and looks_like_listing(source_url)
    ):
        roles = _roles(payload, settings)
        try:
            found = discover(
                source_url=source_url,
                roles=roles,
                fetcher=fetcher,
                search=getattr(request.app.state, "search", None),
                settings=settings,
            )
        except ValueError as exc:
            return _error(422, "validation_error", str(exc))
        if found.count >= 2:
            body = _discovery_body(found, roles)
            body["message"] = f"Found {found.count} roles matching your targets."
            return JSONResponse(body)

    try:
        result = ingest(
            db,
            settings,
            source_url=source_url or None,
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
    background.add_task(
        execute_run,
        run_id,
        settings,
        llm,
        getattr(request.app.state, "search", None),
        getattr(request.app.state, "fetcher", None),
    )


def _fetcher(settings) -> Fetcher:
    return Fetcher(
        max_bytes=settings.fetch_max_bytes,
        timeout_s=settings.fetch_timeout_s,
        max_redirects=settings.fetch_max_redirects,
    )


def _roles(payload: dict[str, Any], settings) -> list[str]:
    raw = payload.get("roles")
    if isinstance(raw, str) and raw.strip():
        return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()][:8]
    if isinstance(raw, list):
        roles = [str(item).strip() for item in raw if str(item).strip()]
        if roles:
            return roles[:8]
    return default_roles(settings)


def _discovery_body(found, roles: list[str]) -> dict[str, Any]:
    return {
        **{
            "postings": [
                {
                    "url": post.url,
                    "title": post.title,
                    "company": post.company,
                    "location": post.location,
                    "source": post.source,
                    "preview": post.description[:240],
                }
                for post in found.postings
            ],
            "count": found.count,
            "roles": roles,
            "pages_fetched": found.pages_fetched,
            "queries_used": found.queries_used,
            "skipped": found.skipped,
            "notes": found.notes,
        }
    }


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}
