"""ARQ worker entrypoints for background jobs."""

from __future__ import annotations

from arq.connections import RedisSettings

from arbor.adapters.outbound.arq.runner import execute_import_job
from arbor.env import redis_url


async def process_import_job(_ctx, payload: dict) -> None:
    execute_import_job(payload)


class WorkerSettings:
    functions = [process_import_job]
    redis_settings = RedisSettings.from_dsn(redis_url() or "redis://127.0.0.1:6379/0")
    job_timeout = 600
