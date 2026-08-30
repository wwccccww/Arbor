"""Add encrypted content sampling fields to decision_traces."""

from __future__ import annotations

from alembic import op

revision = "0012_observability_content"
down_revision = "0011_decision_traces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE decision_traces
            ADD COLUMN IF NOT EXISTS encrypted_payload text,
            ADD COLUMN IF NOT EXISTS content_sampled boolean NOT NULL DEFAULT false
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE decision_traces
            DROP COLUMN IF EXISTS content_sampled,
            DROP COLUMN IF EXISTS encrypted_payload
        """
    )
