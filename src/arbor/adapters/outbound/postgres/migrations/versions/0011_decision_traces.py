"""Add decision_traces for observability debug summaries."""

from __future__ import annotations

from alembic import op

revision = "0011_decision_traces"
down_revision = "0010_memory_text_tsv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_traces (
            id uuid PRIMARY KEY,
            request_id text NOT NULL,
            tenant_id uuid NOT NULL REFERENCES tenants (id),
            persona_id uuid REFERENCES personas (id),
            thread_id uuid REFERENCES threads (id),
            message_id text,
            trace_version integer NOT NULL DEFAULT 1,
            summary_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz,
            UNIQUE (tenant_id, request_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS decision_traces_tenant_created
            ON decision_traces (tenant_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS decision_traces_tenant_created")
    op.execute("DROP TABLE IF EXISTS decision_traces")
