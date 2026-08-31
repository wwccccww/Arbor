"""Employee definition publish gate and policy snapshot columns."""

from __future__ import annotations

from alembic import op

revision = "0018_employee_definition_gate"
down_revision = "0017_artifact_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE employee_definitions
            ADD COLUMN IF NOT EXISTS eval_gate_passed boolean NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS eval_report jsonb NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS policy_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS published_at timestamptz,
            ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE employee_definitions
            DROP COLUMN IF EXISTS eval_gate_passed,
            DROP COLUMN IF EXISTS eval_report,
            DROP COLUMN IF EXISTS policy_snapshot,
            DROP COLUMN IF EXISTS published_at,
            DROP COLUMN IF EXISTS updated_at;
        """
    )
