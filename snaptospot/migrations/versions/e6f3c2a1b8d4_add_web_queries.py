"""add web query log and cache

Revision ID: e6f3c2a1b8d4
Revises: d5e2b7a9c1f3
Create Date: 2026-11-16 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f3c2a1b8d4"
down_revision: str | None = "d5e2b7a9c1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "web_queries",
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("gap_key", sa.String(length=120), nullable=False),
        sa.Column("gap_class", sa.String(length=40), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("engine", sa.String(length=40), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("chosen_url", sa.String(length=2048), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("web_queries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_web_queries_tenant_id"), ["tenant_id"])
        batch_op.create_index(batch_op.f("ix_web_queries_run_id"), ["run_id"])
        batch_op.create_index(batch_op.f("ix_web_queries_gap_class"), ["gap_class"])
        batch_op.create_index(batch_op.f("ix_web_queries_query_hash"), ["query_hash"])
        batch_op.create_index(batch_op.f("ix_web_queries_domain"), ["domain"])
        batch_op.create_index(batch_op.f("ix_web_queries_status"), ["status"])
        batch_op.create_index(
            "web_queries_cache",
            ["tenant_id", "domain", "query_hash", "created_at"],
        )
        batch_op.create_index("web_queries_by_run", ["run_id", "gap_class"])


def downgrade() -> None:
    with op.batch_alter_table("web_queries", schema=None) as batch_op:
        batch_op.drop_index("web_queries_by_run")
        batch_op.drop_index("web_queries_cache")
        batch_op.drop_index(batch_op.f("ix_web_queries_status"))
        batch_op.drop_index(batch_op.f("ix_web_queries_domain"))
        batch_op.drop_index(batch_op.f("ix_web_queries_query_hash"))
        batch_op.drop_index(batch_op.f("ix_web_queries_gap_class"))
        batch_op.drop_index(batch_op.f("ix_web_queries_run_id"))
        batch_op.drop_index(batch_op.f("ix_web_queries_tenant_id"))

    op.drop_table("web_queries")
