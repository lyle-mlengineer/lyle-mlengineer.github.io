"""add facts and gap answers

Revision ID: c3a8e1f4d920
Revises: 7b9d2f14c8aa
Create Date: 2026-11-15 11:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'c3a8e1f4d920'
down_revision: str | None = '7b9d2f14c8aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'facts',
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('key', sa.String(length=120), nullable=False),
        sa.Column('value', sa.String(length=600), nullable=False),
        sa.Column('unit', sa.String(length=40), nullable=True),
        sa.Column('label', sa.String(length=160), nullable=False),
        sa.Column('as_of', sa.String(length=40), nullable=True),
        sa.Column('source_type', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=2048), nullable=False),
        sa.Column('source_id', sa.String(length=40), nullable=True),
        sa.Column('source_quote', sa.String(length=2000), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('tier', sa.String(length=1), nullable=False),
        sa.Column('retrieved_at', sa.Date(), nullable=False),
        sa.Column('published_at', sa.Date(), nullable=True),
        sa.Column('permission', sa.String(length=30), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attested_by', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('run_id', 'id'),
    )
    with op.batch_alter_table('facts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_facts_tenant_id'), ['tenant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_facts_key'), ['key'], unique=False)
        batch_op.create_index(batch_op.f('ix_facts_status'), ['status'], unique=False)
        batch_op.create_index(
            'facts_one_accepted',
            ['run_id', 'key'],
            unique=True,
            sqlite_where=sa.text("status = 'accepted'"),
            postgresql_where=sa.text("status = 'accepted'"),
        )
        batch_op.create_index(
            'facts_by_run', ['run_id', 'tier', 'status'], unique=False
        )

    op.create_table(
        'gap_answers',
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('gap_key', sa.String(length=120), nullable=False),
        sa.Column('question_json', sa.JSON(), nullable=False),
        sa.Column('answer_json', sa.JSON(), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('fact_id', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('gap_answers', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_gap_answers_run_id'), ['run_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gap_answers_tenant_id'), ['tenant_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_gap_answers_gap_key'), ['gap_key'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('gap_answers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_gap_answers_gap_key'))
        batch_op.drop_index(batch_op.f('ix_gap_answers_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_gap_answers_run_id'))

    op.drop_table('gap_answers')

    with op.batch_alter_table('facts', schema=None) as batch_op:
        batch_op.drop_index('facts_by_run')
        batch_op.drop_index(
            'facts_one_accepted',
            sqlite_where=sa.text("status = 'accepted'"),
            postgresql_where=sa.text("status = 'accepted'"),
        )
        batch_op.drop_index(batch_op.f('ix_facts_status'))
        batch_op.drop_index(batch_op.f('ix_facts_key'))
        batch_op.drop_index(batch_op.f('ix_facts_tenant_id'))

    op.drop_table('facts')
