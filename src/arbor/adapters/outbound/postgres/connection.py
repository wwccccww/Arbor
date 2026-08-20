from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True, row_factory=dict_row, cursor_factory=psycopg.ClientCursor)


def apply_schema_sql(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def wipe_public_schema(conn: psycopg.Connection) -> None:
    conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
    conn.execute("CREATE SCHEMA public")
    conn.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER")
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
