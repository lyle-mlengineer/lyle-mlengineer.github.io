from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db import Base
from app.models.base import IdMixin, TimestampMixin

_EMBEDDING = Vector(get_settings().embedding_dimensions).with_variant(JSON(), "sqlite")


class Document(Base, IdMixin, TimestampMixin):
    """One file uploaded against a run.

    Documents are tenant-scoped and belong to a single run: the same deck can be
    uploaded to two runs without either seeing the other's chunks. ``status`` is
    ``ready``, ``failed`` or ``expired``; the original file is kept on disk until
    the 30-day expiry job runs, unless the user pins it to the brand.
    """

    __tablename__ = "documents"

    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    pages: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    fact_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready", index=True)
    failure: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(32), default="")
    pinned_to_brand: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    __table_args__ = (Index("documents_by_run", "run_id", "status"),)


class Chunk(Base, IdMixin, TimestampMixin):
    """A retrievable span of a document with page and ordinal metadata.

    ``embedding`` is a pgvector column on Postgres and JSON on SQLite, so tests
    and local development keep working without a vector extension. Retrieval
    filters on ``tenant_id`` and ``run_id`` before it ranks anything.
    """

    __tablename__ = "chunks"

    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[str] = mapped_column(String(32), index=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(30), default="page")
    text: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(_EMBEDDING, nullable=True)

    __table_args__ = (
        Index("chunks_document_ordinal", "document_id", "ordinal"),
        Index("chunks_lookup", "tenant_id", "run_id", "document_id"),
    )
