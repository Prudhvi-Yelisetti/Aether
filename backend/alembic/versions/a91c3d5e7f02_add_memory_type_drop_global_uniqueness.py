"""add memory_type column, drop global (project_id,key) uniqueness

Structural fix for the gap flagged in STATUS.md as far back as item 13
and left open through item 19: the memory table conflated two genuinely
different kinds of stored information under one schema with no way to
tell them apart except by convention (key naming) --

- durable facts about the user (services/memory_extraction.py output:
  name, stated preferences) -- these are context-independent and
  relevant to essentially every request, the way you don't need a
  specific cue to recall your own name.
- skill-run artifacts (SaveMemoryStep's last_research/last_file_digest)
  -- records of a specific past event/task, only relevant when the
  current request actually relates to that event.

This is Tulving's semantic/episodic memory distinction from cognitive
psychology, and it maps directly onto the actual bug: dumping BOTH
kinds into every single prompt (the old behavior, mitigated but not
fixed by item 13's relabeling) is like a person's every thought being
interrupted by an unfiltered replay of every specific thing that ever
happened to them, rather than recalling the general/durable knowledge
that's always active plus only the specific episodes a relevant cue
brings to mind. See services/ollama_service.py and
storage/project_store.py in the same commit for the retrieval-side fix
(episodic rows are now cue-filtered by keyword overlap with the current
prompt, semantic rows are always included).

The existing unique constraint (project_id, key) from f33fab44be66
assumed exactly one row per key -- fine for semantic facts (a name has
one current value), wrong for episodic memory, which needs to keep a
short *history* of recent episodes per key (e.g. the last 3 file
digests, not just the latest one overwriting the prior one every time
-- this is also why the OLD skill-artifact behavior technically already
"forgot" everything except the most recent run of each skill, silently,
which is the wrong kind of forgetting: total loss on overwrite rather
than graceful capacity-bounded decay). So the constraint is dropped
here; storage/project_store.py enforces "one semantic row per key" at
the application level instead (query-then-write, not an atomic
upsert -- an accepted tradeoff for single-user local software with
already-serialized request handling, not safe under real concurrent
writers).

Data migration: existing rows with the two known skill-artifact keys
(last_research, last_file_digest -- see services/skills/*.py's
SaveMemoryStep call sites) are backfilled as 'episodic'; everything
else (arbitrary LLM-extracted fact keys) as 'semantic'.

Revision ID: a91c3d5e7f02
Revises: 44f9e98b07f2
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "a91c3d5e7f02"
down_revision = "44f9e98b07f2"
branch_labels = None
depends_on = None

EPISODIC_KEYS = ("last_research", "last_file_digest")


def upgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.add_column(
            sa.Column("memory_type", sa.String(), nullable=False, server_default="semantic")
        )
        batch_op.drop_constraint("uq_memory_project_key", type_="unique")

    conn = op.get_bind()
    placeholders = ",".join(f"'{k}'" for k in EPISODIC_KEYS)
    conn.execute(sa.text(f"UPDATE memory SET memory_type = 'episodic' WHERE key IN ({placeholders})"))


def downgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.create_unique_constraint("uq_memory_project_key", ["project_id", "key"])
        batch_op.drop_column("memory_type")
