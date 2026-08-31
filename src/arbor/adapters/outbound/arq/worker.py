"""ARQ worker entrypoints for background jobs."""

from __future__ import annotations

from arq.connections import RedisSettings

from arbor.adapters.outbound.arq.agent_runner import execute_agent_run
from arbor.adapters.outbound.arq.runner import execute_import_job
from arbor.env import redis_url


async def process_import_job(_ctx, payload: dict) -> None:
    execute_import_job(payload)


async def process_agent_run(_ctx, payload: dict) -> None:
    execute_agent_run(payload)


async def sweep_object_blobs(_ctx) -> dict:
    from arbor.application.storage.object_gc import (
        object_uris_from_memory_source,
        sweep_orphan_objects,
    )
    from arbor.env import database_url

    if not database_url():
        return {"deleted": [], "skipped": "no database"}
    from arbor.adapters.outbound.object_storage import build_object_storage
    from arbor.adapters.outbound.postgres import PostgresSession

    session = PostgresSession.connect(database_url())
    try:
        storage = build_object_storage(session=session)
        referenced: set[str] = set()
        rows = session.conn.execute("SELECT source FROM memory_items WHERE source IS NOT NULL").fetchall()
        for row in rows:
            source = row["source"]
            if isinstance(source, dict):
                referenced.update(object_uris_from_memory_source(source))
        deleted = sweep_orphan_objects(storage, referenced)
        return {"deleted": deleted, "count": len(deleted)}
    finally:
        session.close()


async def cleanup_decision_traces(_ctx) -> dict:
    from arbor.env import database_url
    from arbor.observability.cleanup import cleanup_expired_traces

    if not database_url():
        return {"deleted": 0, "skipped": "no database"}
    from arbor.adapters.outbound.postgres import PostgresSession

    session = PostgresSession.connect(database_url())
    try:
        from arbor.adapters.outbound.object_storage import build_object_storage

        storage = build_object_storage(session=session)
        deleted = cleanup_expired_traces(session.decision_traces, storage)
        return {"deleted": deleted}
    finally:
        session.close()


class WorkerSettings:
    functions = [
        process_import_job,
        process_agent_run,
        sweep_object_blobs,
        cleanup_decision_traces,
    ]
    redis_settings = RedisSettings.from_dsn(redis_url() or "redis://127.0.0.1:6379/0")
    job_timeout = 600
