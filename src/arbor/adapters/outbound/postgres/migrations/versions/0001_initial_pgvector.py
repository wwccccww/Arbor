"""Initial Postgres + pgvector schema.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

import psycopg
from alembic import op

from arbor.adapters.outbound.postgres.alembic_runner import psycopg_url
from arbor.adapters.outbound.postgres.connection import apply_schema_sql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    url = psycopg_url(op.get_bind().engine.url.render_as_string(hide_password=False))
    ctx = op.get_context()

    def apply() -> None:
        with psycopg.connect(
            url,
            autocommit=True,
            cursor_factory=psycopg.ClientCursor,
            connect_timeout=10,
            options="-c lock_timeout=15s -c statement_timeout=60s",
        ) as conn:
            apply_schema_sql(conn)

    if ctx.as_sql:
        apply()
        return
    with ctx.autocommit_block():
        apply()


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS public CASCADE")
    op.execute("CREATE SCHEMA public")
