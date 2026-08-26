"""Add persona avatar column."""

from __future__ import annotations

from alembic import op

revision = "0009_avatar"
down_revision = "0008_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE personas ADD COLUMN IF NOT EXISTS avatar text NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE personas DROP COLUMN IF EXISTS avatar")
