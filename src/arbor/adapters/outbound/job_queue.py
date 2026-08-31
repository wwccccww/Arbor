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

    def __init__(self, pool: Any, observability: object | None = None) -> None:
        self._pool = pool
        self._observability = observability

    @property
    def is_async(self) -> bool:
        return True

    async def enqueue_import_job_async(self, payload: dict) -> None:
        from arbor.observability.redis import observed_redis

        with observed_redis(self._observability, "enqueue"):
            await self._pool.enqueue_job("process_import_job", payload)

    def enqueue_import_job(self, payload: dict) -> None:
        raise RuntimeError("use enqueue_import_job_async with ArqJobQueue")


class ArqAgentJobQueue:
    """Enqueue agent run advancement for ARQ worker."""

    def __init__(self, pool: Any, observability: object | None = None) -> None:
        self._pool = pool
        self._observability = observability

    @property
    def is_async(self) -> bool:
        return True

    async def enqueue_run_async(
        self,
        tenant_id,
        run_id: str,
        expected_version: int,
        user_id: str,
    ) -> None:
        from arbor.observability.redis import observed_redis

        payload = {
            "tenant_id": tenant_id.value if hasattr(tenant_id, "value") else str(tenant_id),
            "run_id": run_id,
            "expected_version": expected_version,
            "user_id": user_id,
            "request_id": run_id,
        }
        with observed_redis(self._observability, "enqueue"):
            await self._pool.enqueue_job("process_agent_run", payload)

    def enqueue_run(self, tenant_id, run_id: str, expected_version: int, user_id: str | None = None) -> None:
        raise RuntimeError("use enqueue_run_async with ArqAgentJobQueue")


def arq_redis_settings(redis_url: str):
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(redis_url)
