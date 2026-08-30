"""Agent runtime tables and memory_class column."""

from __future__ import annotations

from alembic import op

revision = "0014_agent_runtime"
down_revision = "0013_decision_trace_uri"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE memory_items
        ADD COLUMN IF NOT EXISTS memory_class text;

        CREATE TABLE IF NOT EXISTS agent_runs (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            persona_id uuid NOT NULL,
            thread_id uuid,
            requested_by uuid NOT NULL,
            goal text NOT NULL DEFAULT '',
            status text NOT NULL DEFAULT 'pending',
            current_step int NOT NULL DEFAULT 0,
            max_steps int NOT NULL DEFAULT 8,
            token_budget int NOT NULL DEFAULT 16000,
            consumed_tokens int NOT NULL DEFAULT 0,
            cost_budget_micros bigint NOT NULL DEFAULT 0,
            consumed_cost_micros bigint NOT NULL DEFAULT 0,
            version int NOT NULL DEFAULT 1,
            employee_definition_version text,
            final_output jsonb,
            failure jsonb,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        );

        CREATE TABLE IF NOT EXISTS agent_steps (
            id text PRIMARY KEY,
            run_id text NOT NULL REFERENCES agent_runs(id),
            tenant_id uuid NOT NULL,
            persona_id uuid NOT NULL,
            sequence int NOT NULL,
            kind text NOT NULL,
            status text NOT NULL DEFAULT 'pending',
            input jsonb NOT NULL DEFAULT '{}'::jsonb,
            output jsonb NOT NULL DEFAULT '{}'::jsonb,
            observation jsonb NOT NULL DEFAULT '{}'::jsonb,
            retry_count int NOT NULL DEFAULT 0,
            error_kind text,
            error_message text,
            trace_id text,
            started_at timestamptz,
            finished_at timestamptz,
            UNIQUE (run_id, sequence)
        );

        CREATE TABLE IF NOT EXISTS approval_requests (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            run_id text NOT NULL REFERENCES agent_runs(id),
            step_id text NOT NULL,
            persona_id uuid NOT NULL,
            requested_by uuid NOT NULL,
            tool_name text NOT NULL,
            arguments jsonb NOT NULL DEFAULT '{}'::jsonb,
            reason text,
            evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
            status text NOT NULL DEFAULT 'proposed',
            approved_by uuid,
            modified_arguments jsonb,
            expires_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz
        );

        CREATE TABLE IF NOT EXISTS tool_executions (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            run_id text,
            step_id text,
            tool_name text NOT NULL,
            idempotency_key text NOT NULL,
            arguments jsonb NOT NULL DEFAULT '{}'::jsonb,
            result jsonb,
            status text NOT NULL DEFAULT 'pending',
            error_kind text,
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            UNIQUE (tenant_id, tool_name, idempotency_key)
        );

        CREATE INDEX IF NOT EXISTS agent_runs_scope ON agent_runs (tenant_id, persona_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS agent_steps_run ON agent_steps (tenant_id, run_id, sequence);
        CREATE INDEX IF NOT EXISTS approval_requests_pending ON approval_requests (tenant_id, status, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS tool_executions;
        DROP TABLE IF EXISTS approval_requests;
        DROP TABLE IF EXISTS agent_steps;
        DROP TABLE IF EXISTS agent_runs;
        ALTER TABLE memory_items DROP COLUMN IF EXISTS memory_class;
        """
    )
