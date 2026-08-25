"""Persistent sessions, import jobs, eval runs, and object blobs.

Revision ID: 0006_persistence
Revises: 0005_unbounded_embedding
"""

from __future__ import annotations

from alembic import op

revision = "0006_persistence"
down_revision = "0005_unbounded_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS object_blobs (
            key text PRIMARY KEY,
            tenant_id uuid,
            persona_id uuid,
            data bytea NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            access_token text PRIMARY KEY,
            refresh_token text NOT NULL UNIQUE,
            user_id uuid NOT NULL REFERENCES users (id),
            tenant_id uuid NOT NULL,
            role text NOT NULL,
            email text NOT NULL DEFAULT '',
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS import_jobs (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            persona_id uuid NOT NULL,
            filename text NOT NULL DEFAULT '',
            object_uri text,
            hint text,
            status text NOT NULL DEFAULT 'completed',
            inbox_created int NOT NULL DEFAULT 0,
            error text,
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS eval_runs (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            suite_version text NOT NULL,
            strategy text NOT NULL,
            mode text NOT NULL DEFAULT 'retrieval',
            status text NOT NULL DEFAULT 'completed',
            metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
            p0_tenant_leak_zero boolean NOT NULL DEFAULT false,
            cases jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS eval_runs")
    op.execute("DROP TABLE IF EXISTS import_jobs")
    op.execute("DROP TABLE IF EXISTS auth_sessions")
    op.execute("DROP TABLE IF EXISTS object_blobs")
