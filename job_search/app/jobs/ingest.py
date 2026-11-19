"""Job intake: validate, canonicalise, fetch, dedupe, then queue extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Job, JobEvent, Source, utcnow
from ..providers.fetch.http import Fetcher, FetchError
from ..utils import canonicalize_url, provisional_title, sha1, slugify
from .pipeline import RunError, create_run

logger = logging.getLogger("skipper.jobs")

MIN_TEXT = 200
MAX_TEXT = 60_000


class IngestError(ValueError):
    def __init__(self, message: str, *, code: str = "validation_error") -> None:
        self.code = code
        super().__init__(message)


class DuplicateJob(IngestError):
    def __init__(self, job: Job) -> None:
        self.job = job
        super().__init__("That job is already tracked.", code="duplicate_job")


@dataclass
class IngestResult:
    job: Job
    run_id: int
    attached: bool = False
    warning: str | None = None


def ingest(
    db: Session,
    settings: Settings,
    *,
    source_url: str | None,
    source_text: str | None,
    fetcher: Fetcher,
    attach: bool = False,
) -> IngestResult:
    url = (source_url or "").strip()
    text = (source_text or "").strip()
    if bool(url) == bool(text):
        raise IngestError("Provide either a job link or the posting text, not both.")

    warning = None
    page_title = ""
    description_md = None
    source_type = "text"

    if url:
        if len(url) > 2048:
            raise IngestError("That link is longer than 2,048 characters.")
        try:
            canonical = canonicalize_url(url)
        except ValueError as exc:
            raise IngestError(str(exc)) from exc
        try:
            fetched = fetcher.fetch(canonical)
        except FetchError as exc:
            raise IngestError(f"Could not read that link: {exc}") from exc
        if not fetched.ok:
            raise IngestError(
                "Could not read a job description from that page — paste the text instead.",
                code="unreadable_page",
            )
        text = fetched.text
        page_title = fetched.title
        description_md = fetched.page.description_md
        source_url = canonical
        source_type = "website"
        identity = sha1("url|" + canonical)
    else:
        if len(text) < MIN_TEXT:
            raise IngestError(
                f"That looks too short for a job description ({len(text)} characters; "
                f"at least {MIN_TEXT} are needed)."
            )
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT]
            warning = "The posting was longer than 60,000 characters; the end was dropped."
        identity = sha1("text|" + " ".join(text.split()))

    existing = db.scalar(
        select(Job).where(Job.fingerprint == identity, Job.status != "archived")
    )
    if existing is not None:
        if not attach:
            raise DuplicateJob(existing)
        try:
            run = create_run(db, existing)
        except RunError as exc:
            raise IngestError(str(exc), code="conflict") from exc
        db.add(
            JobEvent(
                job_id=existing.id,
                event_type="note",
                note="Attached a new run to an existing job.",
                run_id=run.id,
            )
        )
        db.flush()
        return IngestResult(job=existing, run_id=run.id, attached=True, warning=warning)

    title = provisional_title(page_title or text)
    job = Job(
        title=title,
        slug=_unique_slug(db, slugify(title), identity),
        source_type=source_type,
        source_url=source_url,
        canonical_url=source_url if source_type == "website" else None,
        raw_text=text,
        description_md=description_md,
        fingerprint=identity,
        status="discovered",
    )
    db.add(job)
    db.flush()

    if source_url:
        db.add(
            Source(
                job_id=job.id,
                url=source_url,
                title=page_title or title,
                kind="posting",
                http_status=200,
                text=text,
            )
        )
    db.add(
        JobEvent(
            job_id=job.id,
            event_type="created",
            to_status="discovered",
            note=f"Added from {'link' if source_type == 'website' else 'pasted text'}",
        )
    )
    if warning:
        db.add(JobEvent(job_id=job.id, event_type="note", note=warning))

    try:
        run = create_run(db, job)
    except RunError as exc:
        raise IngestError(str(exc), code="conflict") from exc
    job.updated_at = utcnow()
    db.flush()
    return IngestResult(job=job, run_id=run.id, warning=warning)


def _unique_slug(db: Session, base: str, identity: str) -> str:
    candidate = f"{base}-{identity[:8]}"
    if not db.scalar(select(Job.id).where(Job.slug == candidate)):
        return candidate
    counter = 2
    while db.scalar(select(Job.id).where(Job.slug == f"{candidate}-{counter}")):
        counter += 1
    return f"{candidate}-{counter}"
