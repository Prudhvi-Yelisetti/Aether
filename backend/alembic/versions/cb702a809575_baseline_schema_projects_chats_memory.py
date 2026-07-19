"""baseline schema (projects, chats, memory)

This intentionally has empty upgrade()/downgrade() functions. The tables
already existed (created by the old raw-sqlite3 code) before Alembic was
introduced, with real data in them (25 chats at the time this was written).
Autogenerate wanted to ALTER the live tables to add NOT NULL constraints and
change column type affinities — safe in principle, but not something to run
blind against a database with real rows the first time migrations are wired
up. This revision exists purely as the anchor point ("everything before here
was created outside Alembic"); the database is stamped at this revision
rather than upgraded through it.

Future schema changes (e.g. adding the (project_id, key) unique constraint
for memory upserts in Phase B — see ROADMAP.md) should be their own
migration on top of this one, using batch_alter_table for SQLite.

Revision ID: cb702a809575
Revises:
Create Date: 2026-07-19
"""

revision = "cb702a809575"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # tables already exist; see module docstring


def downgrade() -> None:
    pass
