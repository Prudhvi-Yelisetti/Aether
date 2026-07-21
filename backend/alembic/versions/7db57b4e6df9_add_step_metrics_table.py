"""add step_metrics table

Only the actual new change — purely additive, same as the experiences
table migration (3d051fbf7d64). The NOT NULL / type-affinity diffs
autogenerate found against pre-existing tables are the same cosmetic noise
every prior migration in this project has trimmed out.

Revision ID: 7db57b4e6df9
Revises: 3d051fbf7d64
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op

revision = "7db57b4e6df9"
down_revision = "3d051fbf7d64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "step_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("step_version", sa.String(), nullable=True),
        sa.Column("skill_name", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=True),
        sa.Column("validation_reason", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("step_metrics")
