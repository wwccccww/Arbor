"""Allow embedding column to store bge-m3 (1024) as well as fixture (64).

Revision ID: 0005_unbounded_embedding
Revises: 0004_attachments
"""

from __future__ import annotations

from alembic import op

revision = "0005_unbounded_embedding"
down_revision = "0004_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS memory_items_embedding_hnsw")
    op.execute(
        "ALTER TABLE memory_items ALTER COLUMN embedding TYPE vector USING embedding::vector"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS memory_items_embedding_hnsw")
    op.execute(
        "ALTER TABLE memory_items ALTER COLUMN embedding TYPE vector(64) USING embedding::vector"
    )
