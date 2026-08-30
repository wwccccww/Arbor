from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(
    url: str,
    *,
    connect_timeout: int = 3,
    observability: object | None = None,
) -> psycopg.Connection:
    from arbor.observability.postgres import observe_connection

    conn = psycopg.connect(
        url,
        autocommit=True,
        row_factory=dict_row,
        cursor_factory=psycopg.ClientCursor,
        connect_timeout=connect_timeout,
    )
    return observe_connection(conn, observability)


def reachable(url: str) -> bool:
    try:
        conn = connect(url)
        conn.close()
    except Exception:
        return False
    return True


def apply_schema_sql(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def wipe_public_schema(conn: psycopg.Connection) -> None:
    conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
    conn.execute("CREATE SCHEMA public")
    conn.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER")
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
