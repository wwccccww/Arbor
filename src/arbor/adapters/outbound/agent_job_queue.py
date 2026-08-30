from __future__ import annotations

from typing import Any

from arbor.adapters.outbound.inmemory_agent import SyncAgentJobQueue
from arbor.adapters.outbound.job_queue import ArqAgentJobQueue


class AgentJobQueueHolder:
    def __init__(self, sync_queue: SyncAgentJobQueue) -> None:
        self._sync = sync_queue
        self._queue: Any = sync_queue
        self._user_id: str | None = None

    @property
    def is_async(self) -> bool:
        return self._queue.is_async

    def bind_actor(self, tenant_id, user_id) -> None:
        self._sync.bind_actor(tenant_id, user_id)
        self._user_id = user_id.value if hasattr(user_id, "value") else str(user_id)

    def use_arq(self, arq_queue: ArqAgentJobQueue) -> None:
        self._queue = arq_queue

    def enqueue_run(self, tenant_id, run_id: str, expected_version: int) -> None:
        if isinstance(self._queue, ArqAgentJobQueue):
            raise TypeError("use enqueue_run_async with ArqAgentJobQueue")
        self._sync.enqueue_run(tenant_id, run_id, expected_version)

    async def enqueue_run_async(self, tenant_id, run_id: str, expected_version: int) -> None:
        if isinstance(self._queue, ArqAgentJobQueue):
            await self._queue.enqueue_run_async(
                tenant_id,
                run_id,
                expected_version,
                self._user_id or "",
            )
        else:
            self.enqueue_run(tenant_id, run_id, expected_version)
