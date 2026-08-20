from __future__ import annotations

from typing import Protocol

from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus
from arbor.domain.persona.persona import Persona
from arbor.domain.conversation.thread import Thread
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId


class PersonaRepository(Protocol):
    def get(self, tenant_id: TenantId, persona_id: PersonaId) -> Persona | None: ...
    def save(self, persona: Persona) -> None: ...


class MemoryRepository(Protocol):
    def get(self, tenant_id: TenantId, memory_id: MemoryId) -> MemoryItem | None: ...
    def list_active(self, tenant_id: TenantId, persona_id: PersonaId) -> list[MemoryItem]: ...
    def save(self, item: MemoryItem) -> None: ...
    def delete(self, tenant_id: TenantId, memory_id: MemoryId) -> None: ...


class InboxRepository(Protocol):
    def add(self, item: InboxItem) -> None: ...
    def list_pending(self, tenant_id: TenantId, persona_id: PersonaId) -> list[InboxItem]: ...
    def save(self, item: InboxItem) -> None: ...


class EventGraphRepository(Protocol):
    def list_nodes(self, tenant_id: TenantId, persona_id: PersonaId) -> list[EventNode]: ...
    def add_edge(self, edge: EventEdge) -> None: ...
    def list_edges(self, tenant_id: TenantId, persona_id: PersonaId) -> list[EventEdge]: ...


class ThreadRepository(Protocol):
    def get(self, tenant_id: TenantId, thread_id: ThreadId) -> Thread | None: ...
    def save(self, thread: Thread) -> None: ...


class MemoryHit(Protocol):
    memory: MemoryItem
    score: float


class VectorIndex(Protocol):
    def upsert(self, tenant_id: TenantId, persona_id: PersonaId, memory_id: MemoryId, vector: list[float], status: MemoryStatus) -> None: ...
    def search(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        query_vector: list[float],
        k: int,
        filters: dict | None = None,
    ) -> list[tuple[MemoryItem, float]]: ...
    def delete(self, tenant_id: TenantId, memory_id: MemoryId) -> None: ...


class LLMClient(Protocol):
    def complete(self, *, prompt_slots: dict, text: str, injected_memory_ids: list[str]) -> dict: ...


class ReasoningClient(Protocol):
    def extract(self, text: str) -> dict | None: ...


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...


class ObjectStorage(Protocol):
    def put(self, name: str, data: bytes) -> str: ...
    def count(self) -> int: ...


class Clock(Protocol):
    def now_iso(self) -> str: ...


class IdGenerator(Protocol):
    def new_id(self) -> str: ...


class FaithfulnessScorer(Protocol):
    def score(self, question: str, answer: str, contexts: list[str]) -> float | None: ...
