"""Add audit_logs.

Revision ID: 0003_audit_logs
Revises: 0002_messages
"""

from __future__ import annotations

from alembic import op

revision = "0003_audit_logs"
down_revision = "0002_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            actor_user_id uuid NOT NULL,
            action text NOT NULL,
            resource_type text NOT NULL DEFAULT '',
            resource_id text,
            persona_id uuid,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS audit_logs_tenant_created
            ON audit_logs (tenant_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS audit_logs_tenant_created")
    op.execute("DROP TABLE IF EXISTS audit_logs")
