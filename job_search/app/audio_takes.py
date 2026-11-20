"""Generate the interview audio: plan the turns, speak them, keep the files.

A take is written the same way a run is: a row is created in ``queued``, a
background task claims it, and the page polls for progress. Each turn's WAV lands
on disk before the turn is recorded, so a provider failure halfway through leaves
a playable partial take rather than nothing.

The candidate's own voice is used for the interviewee turns when a reference
recording has been uploaded and the provider can clone it; otherwise the chosen
catalogue voice answers.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import Settings
from .db import session_scope, utcnow
from .jobs.dialogue import (
    PACK_KINDS,
    Turn,
    build_turns,
    payloads_from_artifacts,
    summarise,
)
from .jobs.render import split_paragraphs
from .models import Artifact, AudioTake, Job, Setting
from .models import utcnow as model_utcnow
from .providers.tts.base import TTSProvider, TTSProviderError
from .providers.tts.pricing import speech_cost

logger = logging.getLogger("skipper.audio")

STOPPED = {"ready", "failed"}


class TakeError(RuntimeError):
    """The take could not be created. The message is user-facing."""


def latest_take(db: Session, job_id: int, kind: str | None = None) -> AudioTake | None:
    """The newest take, optionally the newest one that contains ``kind``.

    Scoped takes live alongside whole-pack takes without a schema change: the
    section a turn belongs to is stored in ``turns_json``.
    """
    takes = list(
        db.scalars(
            select(AudioTake)
            .where(AudioTake.job_id == job_id)
            .order_by(AudioTake.created_at.desc(), AudioTake.id.desc())
            .limit(20 if kind else 1)
        )
    )
    if not kind:
        return takes[0] if takes else None
    for take in takes:
        if any(
            isinstance(turn, dict) and turn.get("kind") == kind
            for turn in (take.turns_json or [])
        ):
            return take
    return None


def plan_turns(
    db: Session, job: Job, *, max_turns: int = 14, kind: str | None = None
) -> list[dict[str, Any]]:
    artifacts = list(
        db.scalars(
            select(Artifact).where(Artifact.job_id == job.id, Artifact.is_current.is_(True))
        )
    )
    payloads = payloads_from_artifacts(artifacts)
    if not payloads:
        raise TakeError("The interview pack has not been written yet. Run the pipeline first.")
    if kind and kind not in PACK_KINDS:
        raise TakeError("That interview-pack section does not exist.")
    turns = build_turns(payloads, max_turns=max_turns, only=kind)
    if not turns:
        raise TakeError("This pack has no answers to read out yet.")
    return [turn.as_dict() for turn in turns]


def create_take(
    db: Session,
    job: Job,
    *,
    provider: TTSProvider,
    interviewer_voice: str,
    interviewee_voice: str,
    reference_voice: str | None = None,
    max_turns: int = 14,
    kind: str | None = None,
) -> AudioTake:
    in_flight = db.scalar(
        select(AudioTake)
        .where(AudioTake.job_id == job.id, AudioTake.status.in_(("queued", "generating")))
        .limit(1)
    )
    if in_flight is not None:
        raise TakeError("A take is already being generated for this job.")

    planned = plan_turns(db, job, max_turns=max_turns, kind=kind)
    turns = [
        {
            **turn,
            "voice": interviewer_voice if turn["role"] == "interviewer" else interviewee_voice,
            "direction": list(turn["direction"]),
            "audio": None,
            "duration_ms": 0,
        }
        for turn in planned
    ]
    chars = sum(len(turn["text"]) for turn in turns)
    take = AudioTake(
        job_id=job.id,
        provider=provider.name,
        status="queued",
        interviewer_voice=interviewer_voice,
        interviewee_voice=interviewee_voice,
        reference_voice=reference_voice,
        turns_json=turns,
        chars=chars,
        cost_usd=speech_cost(provider.name, chars),
    )
    db.add(take)
    db.commit()
    return take


def generate_take(
    take_id: int,
    settings: Settings,
    provider: TTSProvider,
    *,
    max_turns: int = 14,
) -> None:
    """Speak a queued take. Safe to call twice: only the first caller claims it."""
    with session_scope(settings) as db:
        claimed = db.execute(
            update(AudioTake)
            .where(AudioTake.id == take_id, AudioTake.status == "queued")
            .values(status="generating")
        )
        db.commit()
        if claimed.rowcount == 0:
            logger.info("audio take %s was already claimed", take_id)
            return

    turns, error = _speak_turns(take_id, settings, provider)

    with session_scope(settings) as db:
        take = db.get(AudioTake, take_id)
        if take is None:
            return
        take.turns_json = turns
        take.chars = sum(len(turn.get("text") or "") for turn in turns)
        take.cost_usd = speech_cost(take.provider, take.chars)
        take.finished_at = model_utcnow()
        if error:
            take.status = "failed"
            take.error = error
        else:
            take.status = "ready"
        db.commit()


def _speak_turns(
    take_id: int,
    settings: Settings,
    provider: TTSProvider,
) -> tuple[list[dict[str, Any]], str | None]:
    with session_scope(settings) as db:
        take = db.get(AudioTake, take_id)
        if take is None:
            return [], "That take no longer exists."
        turns = [dict(turn) for turn in (take.turns_json or [])]
        reference = take.reference_voice

    directory = settings.audio_dir / f"job-{_job_id_for(take_id, settings)}"
    directory.mkdir(parents=True, exist_ok=True)

    for index, turn in enumerate(turns):
        voice = turn.get("voice") or ""
        try:
            speech = provider.synthesize(
                turn["text"],
                voice=voice,
                direction=turn.get("direction") or [],
                reference=reference if turn["role"] == "interviewee" else None,
            )
        except TTSProviderError as exc:
            turn["error"] = str(exc)
            _persist(take_id, settings, turns)
            return turns, f"Stopped at turn {index + 1}: {exc}"
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("turn %s of take %s failed", index, take_id)
            turn["error"] = str(exc)
            _persist(take_id, settings, turns)
            return turns, f"Stopped at turn {index + 1}: {exc}"

        path = directory / f"take-{take_id}-{index}.wav"
        path.write_bytes(speech.audio)
        turn["audio"] = path.name
        turn["duration_ms"] = _duration_ms(speech.audio)
        turn.pop("error", None)
        _persist(take_id, settings, turns)

    return turns, None


def _persist(take_id: int, settings: Settings, turns: list[dict[str, Any]]) -> None:
    """Save progress so the page can play finished turns while others render."""
    with session_scope(settings) as db:
        db.execute(update(AudioTake).where(AudioTake.id == take_id).values(turns_json=list(turns)))
        db.commit()


def _job_id_for(take_id: int, settings: Settings) -> int:
    with session_scope(settings) as db:
        take = db.get(AudioTake, take_id)
        return take.job_id if take is not None else take_id


def turn_audio_path(settings: Settings, take: AudioTake, index: int) -> Path | None:
    turns = take.turns_json or []
    if index < 0 or index >= len(turns):
        return None
    name = turns[index].get("audio")
    if not name:
        return None
    path = settings.audio_dir / f"job-{take.job_id}" / str(name)
    return path if path.exists() else None


# ---------------------------------------------------------------- reference voice


REFERENCE_NAME = "reference.wav"


def reference_path(settings: Settings) -> Path:
    return settings.voices_dir / REFERENCE_NAME


def save_reference(settings: Settings, filename: str, data: bytes) -> Path:
    """Store the uploaded recording. One reference is kept: the newest upload."""
    suffix = Path(filename or "reference.wav").suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".aac", ".opus"}:
        raise TakeError("Upload a WAV, MP3, M4A, FLAC, OGG or WebM recording.")
    if len(data) > 5_000_000:
        raise TakeError("That recording is over 5 MB. Trim it to about a minute.")
    if len(data) < 1_000:
        raise TakeError("That file looks empty.")
    path = reference_path(settings)
    path.write_bytes(data)
    return path


def cloned_voice(db: Session, provider: TTSProvider) -> str | None:
    row = db.get(Setting, _clone_key(provider.name))
    return row.value if row and row.value else None


def store_cloned_voice(db: Session, provider: TTSProvider, voice_id: str) -> None:
    key = _clone_key(provider.name)
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=voice_id, updated_at=utcnow()))
    else:
        row.value = voice_id
        row.updated_at = utcnow()
    db.commit()


def clear_cloned_voice(db: Session, provider: TTSProvider) -> None:
    row = db.get(Setting, _clone_key(provider.name))
    if row is not None:
        db.delete(row)
        db.commit()


def _clone_key(provider_name: str) -> str:
    return f"tts_reference_voice_{re.sub(r'[^a-z0-9_]', '', provider_name.lower())}"


def _duration_ms(wav: bytes) -> int:
    from .providers.tts.audio import duration_ms

    return duration_ms(wav)


def sample_audio(
    settings: Settings,
    provider: TTSProvider,
    voice: str,
    *,
    text: str = "Hi, I'm reading this line so you can hear how I sound.",
) -> Path:
    """A short cached sample so the picker can audition a voice."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", voice)[:80] or "voice"
    path = settings.audio_dir / "samples" / f"{provider.name}-{safe}.wav"
    if path.exists() and path.stat().st_size > 44:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        speech = provider.synthesize(text, voice=voice)
    except TTSProviderError:
        raise
    path.write_bytes(speech.audio)
    return path


def summarise_take(take: AudioTake) -> dict[str, Any]:
    turns = take.turns_json or []
    ready = [turn for turn in turns if turn.get("audio")]
    spoken = [
        Turn(index=i, role=turn.get("role", "interviewee"), section="", text=turn.get("text", ""))
        for i, turn in enumerate(turns)
    ]
    summary = summarise(spoken)
    summary.update(
        {
            "id": take.id,
            "status": take.status,
            "provider": take.provider,
            "error": take.error,
            "ready_turns": len(ready),
            "cost_usd": take.cost_usd,
        }
    )
    return summary


def take_payload(take: AudioTake) -> dict[str, Any]:
    """The take as JSON, with one playable turn per row.

    Shared by the polling endpoint and the job page, so the server-rendered
    markup and the refreshed markup cannot drift apart.
    """
    payload = summarise_take(take)
    payload["turns"] = [
        {
            "index": index,
            "role": turn.get("role"),
            "kind": turn.get("kind") or "",
            "section": turn.get("section"),
            "text": turn.get("text"),
            "paragraphs": split_paragraphs(str(turn.get("text") or ""), 360),
            "direction": list(turn.get("direction") or []),
            "duration_ms": turn.get("duration_ms", 0),
            "error": turn.get("error"),
            "audio_url": (
                f"/api/audio/takes/{take.id}/turns/{index}.wav" if turn.get("audio") else None
            ),
        }
        for index, turn in enumerate(take.turns_json or [])
    ]
    payload["reference"] = bool(take.reference_voice)
    payload["scope"] = _take_scope(take.turns_json or [])
    return payload


def _take_scope(turns: list[dict[str, Any]]) -> str:
    """The one section a take covers, or empty when it covers the whole pack."""
    kinds = {turn.get("kind") for turn in turns if turn.get("kind")}
    return kinds.pop() if len(kinds) == 1 else ""
