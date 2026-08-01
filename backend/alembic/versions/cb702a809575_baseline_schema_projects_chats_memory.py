"""baseline schema (projects, chats, memory)

Originally this had empty upgrade()/downgrade() functions. The tables
already existed (created by the old raw-sqlite3 code) before Alembic was
introduced, with real data in them (25 chats at the time this was written).
Autogenerate wanted to ALTER the live tables to add NOT NULL constraints and
change column type affinities — safe in principle, but not something to run
blind against a database with real rows the first time migrations are wired
up. This revision exists purely as the anchor point ("everything before here
was created outside Alembic"); the existing database was stamped at this
revision rather than upgraded through it.

Bug found live 2026-07-31, while generating a schema-only DB to seed a
packaged build (see STATUS.md): this empty upgrade() meant `alembic upgrade
head` against a genuinely empty database created nothing at all here, then
crashed on f33fab44be66's batch_alter_table("memory") with
NoSuchTableError — because that migration (like every one after it) assumes
this one already created the table. Bootstrapping a brand-new Aether
instance from nothing had silently never worked, and never been tested,
since every session so far built on top of the one pre-Alembic dev
database.

Fixed with idempotent, checkfirst table creation — safe against both cases:
a truly fresh DB (creates the tables) and the existing dev DB (already has
them, so this is a genuine no-op, exactly as it always was). Deliberately
NOT using Base.metadata.create_all() or importing the live ORM models —
migrations should describe the schema as it existed at each historical
point, independent of how the application models have since evolved, so
this spells out the schema as it was at this revision: chats WITHOUT the
capability-trace columns 44f9e98b07f2 adds later, memory WITHOUT the unique
constraint f33fab44be66 adds later.

Future schema changes (e.g. adding the (project_id, key) unique constraint
for memory upserts in Phase B — see ROADMAP.md) should be their own
migration on top of this one, using batch_alter_table for SQLite.

Revision ID: cb702a809575
Revises:
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision = "cb702a809575"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "projects" not in existing:
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
        )

    if "chats" not in existing:
        op.create_table(
            "chats",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.Integer(), nullable=False),
            sa.Column("prompt", sa.String(), nullable=True),
            sa.Column("response", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
        )

    if "memory" not in existing:
        op.create_table(
            "memory",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", sa.String(), nullable=True),
            sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
        )


def downgrade() -> None:
    # Deliberately still a no-op, same as originally. This revision's job
    # is "assert the pre-Alembic baseline exists" — downgrading past it
    # would mean dropping tables that predate migrations entirely on a
    # database where this was a no-op (the common case, the existing dev
    # DB), which is more destructive than useful. If a fresh DB created
    # entirely by this revision's upgrade() ever needs to be torn down,
    # deleting the DB file is the honest equivalent.
    pass
