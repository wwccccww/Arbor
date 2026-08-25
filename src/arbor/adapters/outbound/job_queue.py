from __future__ import annotations

from collections.abc import Callable
from typing import Any


class SyncJobQueue:
    """Run import jobs immediately in the API process (no Redis)."""

    def __init__(self, runner: Callable[[dict], None]) -> None:
        self._runner = runner

    @property
    def is_async(self) -> bool:
        return False

    def enqueue_import_job(self, payload: dict) -> None:
        self._runner(payload)


class ArqJobQueue:
    """Enqueue import jobs for a separate ARQ worker process."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    @property
    def is_async(self) -> bool:
        return True

    async def enqueue_import_job_async(self, payload: dict) -> None:
        await self._pool.enqueue_job("process_import_job", payload)

    def enqueue_import_job(self, payload: dict) -> None:
        raise RuntimeError("use enqueue_import_job_async with ArqJobQueue")


def arq_redis_settings(redis_url: str):
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(redis_url)
