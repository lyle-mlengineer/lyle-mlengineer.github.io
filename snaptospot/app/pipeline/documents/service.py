"""Persist an upload: validate, parse, chunk, embed, store.

Validation happens before anything touches the database, so a rejected file
leaves no half-written document behind.
"""

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditLog, Chunk, Document, Run
from app.models.base import ensure_aware, new_id, utcnow
from app.pipeline.documents import security
from app.pipeline.documents.chunking import chunk_pages
from app.pipeline.documents.embeddings import embed_texts
from app.pipeline.documents.errors import DocumentError
from app.pipeline.documents.parsers import ParsedDocument, parse_document


@dataclass
class IngestedDocument:
    document: Document
    parsed: ParsedDocument


def _audit(
    db: Session,
    run: Run,
    actor_id: str,
    action: str,
    target_id: str,
    meta: dict[str, object],
) -> None:
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action=action,
            target_type="document",
            target_id=target_id,
            meta=meta,
        )
    )


def _storage_path(tenant_id: str, run_id: str, document_id: str, mime: str) -> Path:
    settings = get_settings()
    extension = security.MIME_EXTENSION.get(mime, ".bin")
    root = Path(settings.media_root) / "documents" / tenant_id / run_id
    return root / f"{document_id}{extension}"


def count_active_documents(db: Session, run: Run) -> int:
    rows = db.scalars(
        select(Document.id).where(
            Document.run_id == run.id,
            Document.tenant_id == run.tenant_id,
            Document.status.in_(("ready", "failed")),
        )
    )
    return len(list(rows))


def ingest_upload(
    db: Session,
    run: Run,
    actor_id: str,
    filename: str,
    data: bytes,
    *,
    pin_to_brand: bool = False,
) -> IngestedDocument:
    settings = get_settings()
    name = security.safe_filename(filename)
    if not data:
        raise DocumentError(f"{name}: the file is empty")
    if len(data) > settings.max_document_bytes:
        raise DocumentError(
            f"{name}: {len(data) // (1024 * 1024)} MB exceeds the "
            f"{settings.max_document_bytes // (1024 * 1024)} MB limit",
            status_code=413,
        )

    mime = security.sniff_mime(data, name)
    if mime in {security.DOCX, security.PPTX}:
        security.zip_guard(data)
    security.scan_bytes(data, mime, name)
    parsed = parse_document(data, mime, name)

    drafts = chunk_pages(parsed.pages)
    if not drafts:
        raise DocumentError(f"{name}: no indexable text was found")
    vectors = embed_texts([draft.text for draft in drafts])

    document_id = new_id()
    path = _storage_path(run.tenant_id, run.id, document_id, mime)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        raise DocumentError(f"{name}: could not store the upload") from exc

    now = utcnow()
    document = Document(
        id=document_id,
        tenant_id=run.tenant_id,
        run_id=run.id,
        site_id=run.site_id,
        filename=name,
        mime=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        pages=len(parsed.pages),
        chunk_count=len(drafts),
        fact_count=0,
        status="ready",
        failure=None,
        storage_path=str(path),
        uploaded_by=actor_id,
        pinned_to_brand=pin_to_brand,
        expires_at=(
            None
            if pin_to_brand
            else now + timedelta(days=settings.document_retention_days)
        ),
    )
    db.add(document)
    db.flush()

    for draft, vector in zip(drafts, vectors, strict=True):
        db.add(
            Chunk(
                tenant_id=run.tenant_id,
                run_id=run.id,
                site_id=run.site_id,
                document_id=document.id,
                ordinal=draft.ordinal,
                page=draft.page,
                kind=draft.kind,
                text=draft.text,
                tokens=draft.tokens,
                embedding=vector,
            )
        )
    db.flush()
    _audit(
        db,
        run,
        actor_id,
        "document.uploaded",
        document.id,
        {
            "filename": name,
            "mime": mime,
            "pages": document.pages,
            "chunks": document.chunk_count,
            "bytes": document.size_bytes,
            "pinned_to_brand": pin_to_brand,
            "citations": [
                {"page": page.number, "kind": page.kind} for page in parsed.pages
            ],
        },
    )
    return IngestedDocument(document=document, parsed=parsed)


def record_failure(
    db: Session,
    run: Run,
    actor_id: str,
    filename: str,
    message: str,
) -> Document:
    """Store a rejected upload so the run has an audit trail."""
    settings = get_settings()
    name = security.safe_filename(filename)
    document = Document(
        id=new_id(),
        tenant_id=run.tenant_id,
        run_id=run.id,
        site_id=run.site_id,
        filename=name,
        mime="application/octet-stream",
        size_bytes=0,
        sha256="",
        pages=0,
        chunk_count=0,
        fact_count=0,
        status="failed",
        failure=message[:2000],
        storage_path=None,
        uploaded_by=actor_id,
        pinned_to_brand=False,
        expires_at=utcnow()
        + timedelta(days=settings.document_retention_days),
    )
    db.add(document)
    db.flush()
    _audit(
        db,
        run,
        actor_id,
        "document.rejected",
        document.id,
        {"filename": name, "reason": message},
    )
    return document


def list_documents(db: Session, run: Run) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(
                Document.run_id == run.id,
                Document.tenant_id == run.tenant_id,
            )
            .order_by(Document.created_at, Document.id)
        )
    )


def pin_document(
    db: Session, run: Run, actor_id: str, document: Document, pinned: bool
) -> Document:
    settings = get_settings()
    document.pinned_to_brand = pinned
    document.expires_at = (
        None
        if pinned
        else ensure_aware(document.created_at)
        + timedelta(days=settings.document_retention_days)
    )
    _audit(
        db,
        run,
        actor_id,
        "document.pinned" if pinned else "document.unpinned",
        document.id,
        {"filename": document.filename},
    )
    db.flush()
    return document
