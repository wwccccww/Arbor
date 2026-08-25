from __future__ import annotations

from collections.abc import Callable
from typing import Any

from arbor.adapters.outbound.job_queue import ArqJobQueue, SyncJobQueue


class JobQueueHolder:
    """Mutable queue: sync by default, ARQ when Redis pool is attached at startup."""

    def __init__(self, runner: Callable[[dict], None]) -> None:
        self._queue: Any = SyncJobQueue(runner)

    @property
    def is_async(self) -> bool:
        return self._queue.is_async

    def use_arq(self, arq_queue: ArqJobQueue) -> None:
        self._queue = arq_queue

    async def enqueue_import_job(self, payload: dict) -> None:
        if isinstance(self._queue, ArqJobQueue):
            await self._queue.enqueue_import_job_async(payload)
        else:
            self._queue.enqueue_import_job(payload)
