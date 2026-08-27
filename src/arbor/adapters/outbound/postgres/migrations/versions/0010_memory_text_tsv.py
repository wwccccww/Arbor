"""Add memory_items.text_tsv for Postgres hybrid lexical search."""

from __future__ import annotations

from alembic import op

revision = "0010_memory_text_tsv"
down_revision = "0009_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS text_tsv tsvector")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS memory_items_text_tsv
            ON memory_items USING GIN (text_tsv)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS memory_items_text_tsv")
    op.execute("ALTER TABLE memory_items DROP COLUMN IF EXISTS text_tsv")
