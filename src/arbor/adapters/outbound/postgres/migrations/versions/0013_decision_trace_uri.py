"""Store encrypted decision-trace payloads in object storage."""

from __future__ import annotations

from alembic import op

revision = "0013_decision_trace_uri"
down_revision = "0012_observability_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE decision_traces
            ADD COLUMN IF NOT EXISTS encrypted_payload_uri text
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE decision_traces
            DROP COLUMN IF EXISTS encrypted_payload_uri
        """
    )
