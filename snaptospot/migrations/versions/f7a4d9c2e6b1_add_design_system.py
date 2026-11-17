"""add pinned design system

Revision ID: f7a4d9c2e6b1
Revises: e6f3c2a1b8d4
Create Date: 2026-11-17 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a4d9c2e6b1"
down_revision: str | None = "e6f3c2a1b8d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.add_column(sa.Column("design_system_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("design_system_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.drop_column("design_system_hash")
        batch_op.drop_column("design_system_json")
