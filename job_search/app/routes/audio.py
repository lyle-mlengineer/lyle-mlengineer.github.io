"""Interview audio API: voice picker, take generation and playback.

Everything here is behind the same auth as the rest of the app. Voices are
either fetched from the provider's catalogue or served from a small cache, and
a take is a row plus one WAV per turn under ``var/artifacts/audio``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .. import audio_takes
from ..config import get_settings
from ..deps import get_db, require_api_user, require_csrf
from ..jobs.dialogue import PACK_KINDS
from ..models import AudioTake, Job
from ..providers.tts import registry as tts_registry
from ..providers.tts.base import TTSProvider, TTSProviderError

router = APIRouter(tags=["audio"])


def _tts(request: Request) -> TTSProvider:
    provider: TTSProvider | None = request.app.state.tts
    if provider is None:
        raise HTTPException(status_code=503, detail="no_tts_provider")
    return provider


def _error(http_status: int, code: str, message: str, **details: Any) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=http_status)


def _kind(value: Any) -> str | bool:
    """Empty means the whole pack; False means the caller named a bad section."""
    kind = str(value or "").strip()
    if not kind:
        return ""
    return kind if kind in PACK_KINDS else False


@router.get("/api/tts/voices")
def list_voices(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    session_data = require_api_user(request, db)
    del session_data
    settings = get_settings()
    provider = _tts(request)
    voices = tts_registry.catalogue(provider)
    matched = tts_registry.search_voices(
        voices,
        query=request.query_params.get("q", ""),
        gender=request.query_params.get("gender", ""),
        ethnicity=request.query_params.get("ethnicity", ""),
    )
    return JSONResponse(
        {
            "provider": provider.name,
            "label": tts_registry.PROVIDER_LABELS.get(provider.name, provider.name),
            "note": tts_registry.PROVIDER_NOTES.get(provider.name, ""),
            "supports_clone": provider.supports_clone,
            "max_chars": provider.max_chars,
            "count": len(matched),
            "total": len(voices),
            "voices": [voice.as_dict() for voice in matched],
            "defaults": {
                "interviewer": settings.tts_voice_interviewer or _default_by_role(matched, "interviewer"),
                "interviewee": settings.tts_voice_interviewee or _default_by_role(matched, "interviewee"),
            },
        },
    )


def _default_by_role(voices: list[Any], role: str) -> str:
    """Same defaults as the page: first voice with a fitting gender, else first."""
    pref = "male" if role == "interviewer" else "female"
    for voice in voices:
        if voice.gender == pref:
            return voice.id
    return voices[0].id if voices else ""


@router.get("/api/tts/voices/{voice_id}/sample")
def sample_voice(request: Request, voice_id: str, db: Session = Depends(get_db)) -> FileResponse:
    session_data = require_api_user(request, db)
    del session_data
    settings = get_settings()
    provider = _tts(request)
    try:
        path = audio_takes.sample_audio(settings, provider, voice_id)
    except TTSProviderError as exc:
        return _error(502, "tts_failed", str(exc))
    return FileResponse(path, media_type="audio/wav")


@router.get("/api/jobs/{job_id}/audio")
def get_take(job_id: int, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    session_data = require_api_user(request, db)
    del session_data
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    kind = _kind(request.query_params.get("kind"))
    if kind is False:
        return _error(400, "bad_kind", "That interview-pack section does not exist.")
    take = audio_takes.latest_take(db, job_id, kind=kind or None)
    if take is None:
        return JSONResponse({"job_id": job_id, "kind": kind, "take": None})
    return JSONResponse(
        {"job_id": job_id, "kind": kind, "take": audio_takes.take_payload(take)}
    )


@router.post("/api/jobs/{job_id}/audio", status_code=202)
async def create_take_route(
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
    settings = get_settings()
    provider = _tts(request)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    interviewer = str(body.get("interviewer") or "") or settings.tts_voice_interviewer
    interviewee = str(body.get("interviewee") or "") or settings.tts_voice_interviewee
    kind = _kind(body.get("kind"))
    if kind is False:
        return _error(400, "bad_kind", "That interview-pack section does not exist.")
    if not interviewer or not interviewee:
        return _error(400, "missing_voice", "Pick an interviewer voice and an interviewee voice.")
    try:
        take = audio_takes.create_take(
            db,
            job,
            provider=provider,
            interviewer_voice=interviewer,
            interviewee_voice=interviewee,
            reference_voice=audio_takes.cloned_voice(db, provider),
            max_turns=settings.tts_max_turns,
            kind=kind or None,
        )
    except audio_takes.TakeError as exc:
        return _error(409, "conflict", str(exc), job_id=job.id)

    def _generate() -> None:
        audio_takes.generate_take(take.id, settings, provider, max_turns=settings.tts_max_turns)

    background.add_task(_generate)
    return JSONResponse(
        {
            "job_id": job.id,
            "take_id": take.id,
            "poll_url": f"/api/jobs/{job.id}/audio",
        },
        status_code=202,
    )


@router.get("/api/audio/takes/{take_id}/turns/{index}.wav")
def turn_audio(take_id: int, index: int, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    session_data = require_api_user(request, db)
    del session_data
    settings = get_settings()
    take = db.get(AudioTake, take_id)
    if take is None:
        raise HTTPException(status_code=404, detail="not_found")
    path = audio_takes.turn_audio_path(settings, take, index)
    if path is None:
        raise HTTPException(status_code=404, detail="turn_has_no_audio")
    return FileResponse(path, media_type="audio/wav")


@router.get("/api/voices/reference")
def reference_status(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    session_data = require_api_user(request, db)
    del session_data
    settings = get_settings()
    provider = _tts(request)
    path = audio_takes.reference_path(settings)
    return JSONResponse(
        {
            "exists": path.exists(),
            "clone_supported": provider.supports_clone,
            "cloned_voice": audio_takes.cloned_voice(db, provider),
        }
    )


@router.post("/api/voices/reference")
async def upload_reference(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    session_data = require_api_user(request, db)
    require_csrf(request, session_data)
    settings = get_settings()
    provider = _tts(request)
    form = await request.form()
    upload: UploadFile | None = form.get("file")
    if upload is None or not upload.filename:
        return _error(400, "no_file", "Choose a recording to upload.")
    data = await upload.read()
    try:
        path = audio_takes.save_reference(settings, upload.filename, data)
    except audio_takes.TakeError as exc:
        return _error(400, "bad_reference", str(exc))

    cloned: str | None = None
    note = "Reference saved. It will be used for your parts from now on."
    if provider.supports_clone:
        try:
            cloned = provider.clone_reference(str(path), name="My voice (Skipper)")
            audio_takes.store_cloned_voice(db, provider, cloned)
            note = "Reference saved and cloned. Your parts will use your own voice."
        except TTSProviderError as exc:
            audio_takes.clear_cloned_voice(db, provider)
            note = f"Reference saved, but it could not be cloned: {exc}"
    return JSONResponse(
        {
            "saved": True,
            "cloned": cloned is not None,
            "cloned_voice": cloned,
            "note": note,
            "provider": provider.name,
        }
    )