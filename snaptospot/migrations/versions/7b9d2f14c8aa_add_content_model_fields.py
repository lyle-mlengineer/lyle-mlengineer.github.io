"""add content model fields to runs

Revision ID: 7b9d2f14c8aa
Revises: 4360c82be28d
Create Date: 2026-11-15 10:12:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '7b9d2f14c8aa'
down_revision: str | None = '4360c82be28d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_model_json', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column('model_versions_json', sa.JSON(), nullable=False, server_default='{}')
        )


def downgrade() -> None:
    with op.batch_alter_table('runs', schema=None) as batch_op:
        batch_op.drop_column('model_versions_json')
        batch_op.drop_column('content_model_json')
