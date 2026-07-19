"""add unique constraint on memory(project_id, key)

Only the actual intended change — the unique constraint that makes memory
upserts possible (see services/memory_extraction.py and
storage/project_store.py). The other diffs autogenerate found (NOT NULL,
TEXT->String) are cosmetic SQLAlchemy type-affinity differences against a
table Alembic didn't create, not real changes, so they're left out here
rather than run against live data for no reason.

SQLite requires batch mode (table rebuild) to add a constraint to an
existing table — a plain op.create_unique_constraint() would fail.

Revision ID: f33fab44be66
Revises: cb702a809575
Create Date: 2026-07-19
"""

from alembic import op

revision = "f33fab44be66"
down_revision = "cb702a809575"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.create_unique_constraint("uq_memory_project_key", ["project_id", "key"])


def downgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.drop_constraint("uq_memory_project_key", type_="unique")
