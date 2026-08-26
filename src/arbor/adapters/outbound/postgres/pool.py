from __future__ import annotations

import os

from psycopg.rows import dict_row

from arbor.adapters.outbound.postgres.connection import connect


def pool_size_from_env() -> int:
    raw = (os.environ.get("ARBOR_PG_POOL_SIZE") or "").strip()
    if not raw:
        return 8
    try:
        return max(1, min(32, int(raw)))
    except ValueError:
        return 8


def open_pool(url: str, *, max_size: int | None = None):
    from psycopg_pool import ConnectionPool

    size = max_size if max_size is not None else pool_size_from_env()
    return ConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=size,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
        },
        open=True,
    )
