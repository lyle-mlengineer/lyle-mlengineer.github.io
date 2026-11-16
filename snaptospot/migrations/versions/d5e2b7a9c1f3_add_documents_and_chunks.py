"""add documents, chunks and fact page citations

Revision ID: d5e2b7a9c1f3
Revises: c3a8e1f4d920
Create Date: 2026-11-15 16:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.config import get_settings

revision: str = "d5e2b7a9c1f3"
down_revision: str | None = "c3a8e1f4d920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DIMENSIONS = get_settings().embedding_dimensions


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    postgres = _is_postgres()
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("fact_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("uploaded_by", sa.String(length=32), nullable=False),
        sa.Column("pinned_to_brand", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_documents_tenant_id"), ["tenant_id"])
        batch_op.create_index(batch_op.f("ix_documents_run_id"), ["run_id"])
        batch_op.create_index(batch_op.f("ix_documents_site_id"), ["site_id"])
        batch_op.create_index(batch_op.f("ix_documents_status"), ["status"])
        batch_op.create_index(batch_op.f("ix_documents_expires_at"), ["expires_at"])
        batch_op.create_index("documents_by_run", ["run_id", "status"])

    op.create_table(
        "chunks",
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("site_id", sa.String(length=32), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column(
            "embedding",
            Vector(_DIMENSIONS) if postgres else sa.JSON(),
            nullable=True,
        ),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_chunks_tenant_id"), ["tenant_id"])
        batch_op.create_index(batch_op.f("ix_chunks_run_id"), ["run_id"])
        batch_op.create_index(batch_op.f("ix_chunks_site_id"), ["site_id"])
        batch_op.create_index(batch_op.f("ix_chunks_document_id"), ["document_id"])
        batch_op.create_index("chunks_document_ordinal", ["document_id", "ordinal"])
        batch_op.create_index("chunks_lookup", ["tenant_id", "run_id", "document_id"])

    if postgres:
        op.execute(
            "CREATE INDEX chunks_embedding ON chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX chunks_fts ON chunks "
            "USING gin (to_tsvector('english', text))"
        )

    with op.batch_alter_table("facts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_page", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("facts", schema=None) as batch_op:
        batch_op.drop_column("source_page")

    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS chunks_fts")
        op.execute("DROP INDEX IF EXISTS chunks_embedding")

    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.drop_index("chunks_lookup")
        batch_op.drop_index("chunks_document_ordinal")
        batch_op.drop_index(batch_op.f("ix_chunks_document_id"))
        batch_op.drop_index(batch_op.f("ix_chunks_site_id"))
        batch_op.drop_index(batch_op.f("ix_chunks_run_id"))
        batch_op.drop_index(batch_op.f("ix_chunks_tenant_id"))

    op.drop_table("chunks")

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index("documents_by_run")
        batch_op.drop_index(batch_op.f("ix_documents_expires_at"))
        batch_op.drop_index(batch_op.f("ix_documents_status"))
        batch_op.drop_index(batch_op.f("ix_documents_site_id"))
        batch_op.drop_index(batch_op.f("ix_documents_run_id"))
        batch_op.drop_index(batch_op.f("ix_documents_tenant_id"))

    op.drop_table("documents")
