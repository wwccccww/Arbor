"""Artifact evidence chain and employee definition versions."""

from __future__ import annotations

from alembic import op

revision = "0016_artifacts_evidence"
down_revision = "0015_agent_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            persona_id uuid NOT NULL,
            object_uri text NOT NULL,
            mime_type text NOT NULL DEFAULT '',
            checksum text NOT NULL DEFAULT '',
            parser text NOT NULL DEFAULT '',
            parser_version text NOT NULL DEFAULT '',
            status text NOT NULL DEFAULT 'active',
            supersedes text,
            created_by uuid,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS artifact_segments (
            id text PRIMARY KEY,
            artifact_id text NOT NULL REFERENCES artifacts(id),
            tenant_id uuid NOT NULL,
            persona_id uuid NOT NULL,
            modality text NOT NULL DEFAULT 'text',
            text text NOT NULL DEFAULT '',
            page_number int,
            time_start_ms int,
            time_end_ms int,
            bounding_box jsonb,
            confidence double precision,
            derived_by text NOT NULL DEFAULT '',
            memory_id text,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS artifact_lineage (
            id text PRIMARY KEY,
            tenant_id uuid NOT NULL,
            artifact_id text NOT NULL REFERENCES artifacts(id),
            segment_id text,
            run_id text,
            step_id text,
            memory_id text,
            citation_kind text NOT NULL DEFAULT 'evidence',
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS employee_definitions (
            tenant_id uuid NOT NULL,
            persona_id uuid NOT NULL,
            version text NOT NULL,
            role text NOT NULL DEFAULT '',
            definition jsonb NOT NULL DEFAULT '{}'::jsonb,
            release_status text NOT NULL DEFAULT 'published',
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, persona_id, version)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS employee_definitions;
        DROP TABLE IF EXISTS artifact_lineage;
        DROP TABLE IF EXISTS artifact_segments;
        DROP TABLE IF EXISTS artifacts;
        """
    )
