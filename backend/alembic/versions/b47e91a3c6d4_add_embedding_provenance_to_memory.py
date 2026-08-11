"""add embedding + provenance columns to memory

Two additions in one migration, both extending item 20's semantic/
episodic split (a91c3d5e7f02) rather than changing its shape:

embedding (nullable Text, JSON-encoded float list): computed once at
episodic-write time by services/embedding_service.py (nomic-embed-text,
768 dims) and used by get_relevant_episodic_memory() for cosine-
similarity retrieval instead of the keyword-overlap heuristic that
function shipped with -- see that function's updated docstring in
storage/project_store.py for the full rationale. Semantic rows never
get an embedding: they're always included in full regardless of the
current prompt, so there's nothing to rank them against. Existing
episodic rows are backfilled by a follow-up script (not inline SQL
here, since it needs to call out to Ollama's embedding endpoint) --
rows that never get backfilled just have embedding=NULL and are
skipped at retrieval time, degrading gracefully rather than erroring.

provenance (nullable Text): set on a semantic row when it was written
by the new memory-consolidation feature (services/consolidation_service.py)
rather than directly by extract_memory_facts() or a user statement --
distinguishes "Aether inferred this by summarizing repeated episodic
results" from "the user said this directly." NULL for every row written
before this feature and for every semantic row extract_memory_facts()
writes going forward -- provenance is opt-in metadata added at the
point of write, not backfilled or required.

Revision ID: b47e91a3c6d4
Revises: a91c3d5e7f02
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "b47e91a3c6d4"
down_revision = "a91c3d5e7f02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.add_column(sa.Column("embedding", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("provenance", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.drop_column("provenance")
        batch_op.drop_column("embedding")
