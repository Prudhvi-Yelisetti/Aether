"""add experiences table

Only the actual new change — the additive experiences table (see
db/orm_models.py's Experience model, storage/experience_store.py). Same as
the previous two migrations, the NOT NULL / type-affinity diffs autogenerate
found against pre-existing tables are cosmetic and left out.

This migration is purely additive (CREATE TABLE, no ALTER on existing
tables), so there's no data-loss risk to verify here the way the earlier
two migrations required.

Revision ID: 3d051fbf7d64
Revises: f33fab44be66
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision = "3d051fbf7d64"
down_revision = "f33fab44be66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("prompt", sa.String(), nullable=True),
        sa.Column("tool", sa.String(), nullable=True),
        sa.Column("tool_source", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("experiences")
