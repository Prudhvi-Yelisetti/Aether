"""add attachment_notices column to chats

Persists item 18's attachment_notices (main.py's ChatRequest handler) --
UI-facing warnings about a truncated file, an OCR-capped scanned PDF, or
a file dropped entirely for budget reasons. Since item 18 these only
ever lived in the live /chat response of the request that triggered
them; reopening a past chat never showed them, even though the same
truncation/dropping had genuinely happened to that stored response.
Flagged as a known gap in HANDOFF.md's Next steps ever since, closed
here (STATUS.md item 27).

JSON-encoded list of strings (same encoding choice as embedding/
provenance in b47e91a3c6d4) rather than a separate table -- this is
small, per-chat, display-only data, not something ever queried or
filtered on independently of its parent chat row.

Revision ID: e5f8a2c91b3d
Revises: b47e91a3c6d4
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f8a2c91b3d"
down_revision = "b47e91a3c6d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.add_column(sa.Column("attachment_notices", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.drop_column("attachment_notices")
