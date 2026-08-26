"""Persistent import job metadata for multimodal parsing."""

from __future__ import annotations

from alembic import op

revision = "0007_multimodal_meta"
down_revision = "0006_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE import_jobs ADD COLUMN IF NOT EXISTS parser text")
    op.execute("ALTER TABLE import_jobs ADD COLUMN IF NOT EXISTS media_kind text")
    op.execute("ALTER TABLE import_jobs ADD COLUMN IF NOT EXISTS chunks_parsed int NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE import_jobs DROP COLUMN IF EXISTS chunks_parsed")
    op.execute("ALTER TABLE import_jobs DROP COLUMN IF EXISTS media_kind")
    op.execute("ALTER TABLE import_jobs DROP COLUMN IF EXISTS parser")
