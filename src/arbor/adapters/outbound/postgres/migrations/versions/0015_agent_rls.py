"""RLS for agent tables."""

from __future__ import annotations

from alembic import op

revision = "0015_agent_rls"
down_revision = "0014_agent_runtime"
branch_labels = None
depends_on = None

_TABLES = (
    "agent_runs",
    "agent_steps",
    "approval_requests",
    "tool_executions",
)

_POLICY = """
    CREATE POLICY arbor_tenant_isolation ON {table}
    FOR ALL
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = current_setting('app.tenant_id')::uuid
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NULL
        OR current_setting('app.tenant_id', true) = ''
        OR tenant_id = current_setting('app.tenant_id')::uuid
    )
"""


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(_POLICY.format(table=table))


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS arbor_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
