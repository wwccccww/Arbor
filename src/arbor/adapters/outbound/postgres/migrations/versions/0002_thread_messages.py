"""Persist thread messages.

Revision ID: 0002_messages
Revises: 0001_initial
"""

from __future__ import annotations

from alembic import op

revision = "0002_messages"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            thread_id uuid NOT NULL REFERENCES threads (id) ON DELETE CASCADE,
            role text NOT NULL,
            content text NOT NULL DEFAULT '',
            citation_memory_ids uuid[] NOT NULL DEFAULT '{}',
            citation_event_ids uuid[] NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messages")
