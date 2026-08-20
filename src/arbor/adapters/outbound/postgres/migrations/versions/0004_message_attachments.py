"""Persist chat message attachments.

Revision ID: 0004_attachments
Revises: 0003_audit_logs
"""

from __future__ import annotations

from alembic import op

revision = "0004_attachments"
down_revision = "0003_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS attachments jsonb NOT NULL DEFAULT '[]'::jsonb
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS attachments")
