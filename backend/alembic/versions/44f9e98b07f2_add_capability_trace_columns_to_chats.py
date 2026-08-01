"""add capability trace columns to chats

Adds the same capability/decision fields the /chat response already
returns for a live message (capability_type, capability_name,
capability_source, attempts, escalated -- exposed 2026-07-26, see
STATUS.md) plus llm_validation (the opt-in E2 judge's verdict, if it
ran) to the chats table itself, so a *historical* message loaded from
/project/{id}/chats can show the same CapabilityTrace the frontend
already renders for a fresh one. Previously this data was computed on
every request and returned once, then discarded -- reloading an old
chat had no way to show how that response was actually produced.

All nullable: every row written before this migration has NULL for all
six, and the frontend already treats a missing capability_type as "no
trace to show" (see CapabilityTrace.js), so old messages just render
without a trace instead of a broken one.

Revision ID: 44f9e98b07f2
Revises: 7db57b4e6df9
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op

revision = "44f9e98b07f2"
down_revision = "7db57b4e6df9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.add_column(sa.Column("capability_type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("capability_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("capability_source", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("attempts", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("escalated", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("llm_validation", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.drop_column("llm_validation")
        batch_op.drop_column("escalated")
        batch_op.drop_column("attempts")
        batch_op.drop_column("capability_source")
        batch_op.drop_column("capability_name")
        batch_op.drop_column("capability_type")
