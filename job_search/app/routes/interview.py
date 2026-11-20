"""Interview study API: uploaded sources, practice sets and answer lookup.

Everything is behind the same session and CSRF checks as the rest of the app.
Uploads are read once, extracted to text, chunked and indexed; the original file
is kept for provenance. Generation is synchronous: a practice set is 8 questions,
so the browser can wait for it and show the real failure when one happens.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..deps import get_db, require_api_user, require_csrf
from ..interview.sources import (
    SourceError,
    add_from_upload,
    add_source,
    delete_source,
    question_payload,
    source_payload,
)
from ..interview.study import StudyError, answer_follow_ups, answer_question, generate_questions
from ..models import Company, InterviewQuestion, InterviewSource, Job
from ..providers.fetch.http import FetchError
from ..providers.tts import registry as tts_registry
from ..providers.tts.base import TTSProvider, TTSProviderError

router = APIRouter(tags=["interview"])


def _error(http_status: int, code: str, message: str, **details: Any) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=http_status)


def _llm(request: Request):
    provider = getattr(request.app.state, "llm", None)
    if provider is None:
        raise HTTPException(status_code=503, detail="provider_not_configured")
    return provider


def _job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    return job


def _company_name(db: Session, job: Job) -> str | None:
    if not job.company_id:
        return None
    company = db.get(Company, job.company_id)
    return company.name if company else None


def _int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _seed(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _source_ids(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    ids = []
    for item in value:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids or None


@router.get("/api/interview/sources")
def list_sources(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_api_user(request, db)
    counts = dict(
        db.execute(
            select(InterviewQuestion.source_id, func.count(InterviewQuestion.id))
            .where(InterviewQuestion.source_id.is_not(None))
            .group_by(InterviewQuestion.source_id)
        ).all()
    )
    sources = db.scalars(
        select(InterviewSource).order_by(InterviewSource.created_at.desc())
    ).all()
    return JSONResponse(
        {
            "count": len(sources),
            "sources": [source_payload(source, question_count=counts.get(source.id, 0)) for source in sources],
        }
    )


@router.post("/api/interview/sources", status_code=201)
async def create_source(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    settings = get_settings()

    try:
        form = await request.form()
    except Exception:
        return _error(400, "bad_form", "The upload could not be read.")

    title = str(form.get("title") or "").strip()
    upload = form.get("file")
    text = str(form.get("text") or "").strip()
    url = str(form.get("url") or "").strip()

    try:
        if upload is not None and getattr(upload, "filename", ""):
            data = await upload.read()
            if not data:
                return _error(400, "empty_file", "That file is empty.")
            if len(data) > settings.interview_max_upload_bytes:
                return _error(
                    413,
                    "too_large",
                    f"That file is larger than the {settings.interview_max_upload_bytes // 1_000_000} MB limit.",
                )
            source = add_from_upload(
                db,
                settings,
                filename=upload.filename,
                mime=getattr(upload, "content_type", "") or "",
                data=data,
                title=title,
            )
        elif text:
            source = add_source(
                db,
                settings,
                title=title or "Pasted interview notes",
                text=text,
                kind="markdown" if str(form.get("kind") or "") == "markdown" else "text",
            )
        elif url:
            fetcher = getattr(request.app.state, "fetcher", None)
            if fetcher is None:
                return _error(503, "fetch_unavailable", "The page fetcher is not configured.")
            result = fetcher.fetch(url)
            source = add_source(
                db,
                settings,
                title=title or result.title or url,
                text=result.text,
                kind="article",
                source_url=result.final_url,
            )
        else:
            return _error(
                422,
                "nothing_to_add",
                "Choose a file, paste text, or give an article link.",
            )
    except SourceError as exc:
        db.rollback()
        return _error(422, "source_error", str(exc))
    except FetchError as exc:
        db.rollback()
        return _error(422, "fetch_failed", str(exc))

    db.commit()
    return JSONResponse({"source": source_payload(source)}, status_code=201)


@router.delete("/api/interview/sources/{source_id}")
def remove_source(
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    source = db.get(InterviewSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="not_found")
    delete_source(db, source)
    db.commit()
    return JSONResponse({"deleted": True, "source_id": source_id})


@router.get("/api/interview/sources/{source_id}")
def get_source(source_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    require_api_user(request, db)
    source = db.get(InterviewSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="not_found")
    return JSONResponse({"source": source_payload(source)})


@router.post("/api/interview/sources/{source_id}/questions", status_code=201)
def questions_from_source(
    source_id: int,
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    payload = body or {}
    source = db.get(InterviewSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="not_found")
    llm = _llm(request)
    settings = get_settings()

    job = None
    company = None
    if payload.get("job_id") not in (None, ""):
        job = _job(db, int(payload["job_id"]))
        company = _company_name(db, job)

    try:
        questions = generate_questions(
            db,
            settings,
            llm,
            job=job,
            company=company,
            source_ids=[source.id],
            source_id=source.id,
            count=_int(payload.get("count"), default=5, low=1, high=10),
            difficulty=str(payload.get("difficulty") or "mixed"),
            focus=str(payload.get("focus") or source.title),
            seed=_seed(payload.get("seed")),
            origin="resource",
        )
    except StudyError as exc:
        db.rollback()
        return _error(502, "generation_failed", str(exc))

    return JSONResponse(
        {"source_id": source.id, "questions": [question_payload(question) for question in questions]},
        status_code=201,
    )


@router.post("/api/jobs/{job_id}/interview/practice", status_code=201)
def generate_practice(
    job_id: int,
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    payload = body or {}
    job = _job(db, job_id)
    llm = _llm(request)
    settings = get_settings()

    try:
        questions = generate_questions(
            db,
            settings,
            llm,
            job=job,
            company=_company_name(db, job),
            source_ids=_source_ids(payload.get("source_ids")),
            count=_int(
                payload.get("count"),
                default=settings.interview_practice_questions,
                low=1,
                high=12,
            ),
            difficulty=str(payload.get("difficulty") or "mixed"),
            focus=str(payload.get("focus") or ""),
            seed=_seed(payload.get("seed")),
            origin="practice",
        )
    except StudyError as exc:
        db.rollback()
        return _error(502, "generation_failed", str(exc))

    return JSONResponse(
        {"job_id": job.id, "questions": [question_payload(question) for question in questions]},
        status_code=201,
    )


@router.post("/api/jobs/{job_id}/interview/answer")
def find_answer(
    job_id: int,
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    payload = body or {}
    job = _job(db, job_id)
    llm = _llm(request)
    settings = get_settings()

    try:
        result = answer_question(
            db,
            settings,
            llm,
            job=job,
            company=_company_name(db, job),
            question=str(payload.get("question") or ""),
            source_ids=_source_ids(payload.get("source_ids")),
        )
    except StudyError as exc:
        return _error(422, "answer_failed", str(exc))

    return JSONResponse(result)


@router.post("/api/interview/questions/{question_id}/follow-up-answers")
def follow_up_answers(
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Write, cache and return an answer for each follow-up beneath a question.

    Answers are generated lazily when the collapsible section is opened, so a
    practice set with eight questions does not pay for twenty follow-up answers
    up front. The result is persisted, and later openings are free.
    """
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    row = db.get(InterviewQuestion, question_id)
    if row is None:
        return _error(404, "not_found", "That question no longer exists.")

    cached = list(row.follow_up_answers_json or [])
    if cached:
        return JSONResponse({"question_id": row.id, "answers": cached})

    follow_ups = [str(item).strip() for item in (row.follow_ups_json or []) if str(item).strip()]
    if not follow_ups:
        return _error(422, "no_follow_ups", "This question has no follow-ups to answer.")

    job = db.get(Job, row.job_id) if row.job_id else None
    try:
        answers = answer_follow_ups(
            db,
            get_settings(),
            _llm(request),
            job=job,
            company=_company_name(db, job) if job else None,
            question=row.question,
            answer=row.answer,
            follow_ups=follow_ups,
            source_ids=[row.source_id] if row.source_id else None,
            role=row.role or "",
            level=row.level or "",
        )
    except StudyError as exc:
        return _error(422, "answer_failed", str(exc))

    row.follow_up_answers_json = answers
    db.commit()
    return JSONResponse({"question_id": row.id, "answers": answers})


@router.get("/api/jobs/{job_id}/interview/questions")
def list_questions(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    require_api_user(request, db)
    _job(db, job_id)
    origin = request.query_params.get("origin", "").strip()
    stmt = (
        select(InterviewQuestion)
        .options(selectinload(InterviewQuestion.source))
        .where(InterviewQuestion.job_id == job_id)
        .order_by(InterviewQuestion.created_at.desc())
        .limit(60)
    )
    if origin in {"practice", "resource", "answer"}:
        stmt = stmt.where(InterviewQuestion.origin == origin)
    questions = db.scalars(stmt).all()
    return JSONResponse(
        {"job_id": job_id, "questions": [question_payload(question) for question in questions]}
    )


@router.delete("/api/interview/questions/{question_id}")
def remove_question(
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    question = db.get(InterviewQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(question)
    db.commit()
    return JSONResponse({"deleted": True, "question_id": question_id})


# ------------------------------------------------------------- study workspace


def _tts(request: Request) -> TTSProvider:
    provider: TTSProvider | None = getattr(request.app.state, "tts", None)
    if provider is None:
        raise HTTPException(status_code=503, detail="no_tts_provider")
    return provider


@router.get("/api/study/questions")
def list_study_questions(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Every job-independent question set, newest first."""
    require_api_user(request, db)
    rows = db.scalars(
        select(InterviewQuestion)
        .options(selectinload(InterviewQuestion.source))
        .where(InterviewQuestion.job_id.is_(None))
        .order_by(InterviewQuestion.created_at.desc())
        .limit(60)
    ).all()
    return JSONResponse({"questions": [question_payload(row) for row in rows]})


@router.post("/api/study/questions", status_code=201)
def generate_study_questions(
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Generate a practice set with no job attached, for a role and level."""
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    payload = body or {}
    llm = _llm(request)
    settings = get_settings()

    role = str(payload.get("role") or "").strip()[:120]
    level = str(payload.get("level") or "").strip()[:40]
    try:
        questions = generate_questions(
            db,
            settings,
            llm,
            job=None,
            source_ids=_source_ids(payload.get("source_ids")),
            count=_int(
                payload.get("count"),
                default=settings.interview_practice_questions,
                low=1,
                high=12,
            ),
            difficulty=str(payload.get("difficulty") or "mixed"),
            focus=str(payload.get("focus") or ""),
            seed=_seed(payload.get("seed")),
            origin="practice",
            role=role,
            level=level,
        )
    except StudyError as exc:
        db.rollback()
        return _error(502, "generation_failed", str(exc))

    return JSONResponse(
        {"role": role, "level": level, "questions": [question_payload(q) for q in questions]},
        status_code=201,
    )


def _resolve_voice(
    provider: TTSProvider,
    settings,
    *,
    requested: str = "",
    role: str = "",
) -> str:
    """Pick a voice the provider actually has.

    A voice saved for another provider (or an old catalogue id) must not fail the
    request: fall back to the configured default and then to the catalogue.
    """
    catalogue = tts_registry.catalogue(provider)
    known = {voice.id for voice in catalogue}
    preferred = (
        settings.tts_voice_interviewee
        if role == "answer"
        else settings.tts_voice_interviewer
    )
    if requested and (not known or requested in known):
        return requested
    if preferred and (not known or preferred in known):
        return preferred
    if catalogue:
        wanted = "female" if role == "answer" else "male"
        return next(
            (voice.id for voice in catalogue if voice.gender.lower() == wanted),
            catalogue[0].id,
        )
    return preferred or requested


@router.post("/api/study/audio")
def study_audio(
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Speak one question or answer on demand, without creating a take row."""
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    body = body or {}

    text = str(body.get("text") or "").strip()
    if len(text) < 2:
        return _error(422, "validation_error", "There is nothing to read out.")
    if len(text) > 6_000:
        return _error(422, "validation_error", "That answer is too long to read in one go.")

    provider = _tts(request)
    settings = get_settings()
    role = str(body.get("role") or "").strip()
    voice = _resolve_voice(
        provider,
        settings,
        requested=str(body.get("voice") or "").strip(),
        role=role,
    )
    if not voice:
        return _error(409, "missing_voice", "No speech voice is available. Pick one in Settings.")

    try:
        speech = provider.synthesize(text, voice=voice)
    except TTSProviderError as exc:
        return _error(502, "tts_failed", str(exc))
    return Response(
        content=speech.audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
