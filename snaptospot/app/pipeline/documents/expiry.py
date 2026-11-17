"""Thirty-day document expiry, skipping anything pinned to the brand."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Chunk, Document
from app.models.base import utcnow


@dataclass
class ExpiryReport:
    expired: int = 0
    files_deleted: int = 0
    documents: list[str] = field(default_factory=list)


def expire_documents(
    db: Session,
    *,
    now: datetime | None = None,
    tenant_id: str | None = None,
    retention_days: int | None = None,
) -> ExpiryReport:
    """Delete chunks and files past their expiry; pinned documents are kept."""
    moment = now or utcnow()
    conditions = [
        Document.pinned_to_brand.is_(False),
        Document.status == "ready",
    ]
    if retention_days is not None:
        conditions.append(
            Document.created_at <= moment - timedelta(days=retention_days)
        )
    else:
        conditions.append(Document.expires_at.is_not(None))
        conditions.append(Document.expires_at <= moment)
    if tenant_id:
        conditions.append(Document.tenant_id == tenant_id)

    documents = list(db.scalars(select(Document).where(*conditions)))
    report = ExpiryReport()
    for document in documents:
        db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        if document.storage_path:
            try:
                Path(document.storage_path).unlink(missing_ok=True)
                report.files_deleted += 1
            except OSError:
                pass
        document.status = "expired"
        document.chunk_count = 0
        document.failure = "expired"
        report.expired += 1
        report.documents.append(document.id)
        db.add(
            AuditLog(
                tenant_id=document.tenant_id,
                actor_user_id=None,
                action="document.expired",
                target_type="document",
                target_id=document.id,
                meta={
                    "filename": document.filename,
                    "pinned_to_brand": document.pinned_to_brand,
                },
            )
        )
    db.flush()
    return report
