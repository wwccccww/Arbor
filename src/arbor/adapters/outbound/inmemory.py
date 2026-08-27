from __future__ import annotations

import json
from dataclasses import dataclass, field

from arbor.domain.audit.log import AuditLog
from arbor.domain.conversation.stream import StreamFinished, chunk_text
from arbor.domain.conversation.thread import Thread
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.identity.tenant import Tenant
from arbor.domain.identity.user import User
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.persona import Persona
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId
from arbor.domain.shared.textvec import cosine, fixture_embed


def _apply_inmemory_filters(item: MemoryItem, filters: dict | None) -> bool:
    if not filters:
        return True
    event_ids = filters.get("event_ids")
    if event_ids is not None:
        allowed = {str(value) for value in event_ids}
        event_id = item.event_id.value if item.event_id else None
        if event_id is None or event_id not in allowed:
            return False
    types = filters.get("types")
    if types is not None:
        allowed_types = {str(value) for value in types}
        if item.type.value not in allowed_types:
            return False
    exclude_ids = filters.get("exclude_ids")
    return exclude_ids is None or item.id.value not in {str(value) for value in exclude_ids}


@dataclass
class InMemoryStores:
    personas: dict[str, Persona] = field(default_factory=dict)
    memories: dict[str, MemoryItem] = field(default_factory=dict)
    inbox: dict[str, InboxItem] = field(default_factory=dict)
    events: dict[str, EventNode] = field(default_factory=dict)
    edges: list[EventEdge] = field(default_factory=list)
    threads: dict[str, Thread] = field(default_factory=dict)
    vectors: dict[str, tuple[str, str, list[float], MemoryStatus]] = field(default_factory=dict)
    objects: dict[str, bytes] = field(default_factory=dict)
    audit_logs: list[AuditLog] = field(default_factory=list)
    tenants: dict[str, Tenant] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)


class InMemoryTenantRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def get(self, tenant_id: TenantId) -> Tenant | None:
        return self.stores.tenants.get(tenant_id.value)

    def list_for_user(self, user_id: UserId) -> list[Tenant]:
        return [
            tenant
            for tenant in self.stores.tenants.values()
            if tenant.member(user_id) is not None
        ]

    def save(self, tenant: Tenant) -> None:
        self.stores.tenants[tenant.id.value] = tenant

    def delete(self, tenant_id: TenantId) -> None:
        self.stores.tenants.pop(tenant_id.value, None)


class InMemoryUserRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def get(self, user_id: UserId) -> User | None:
        return self.stores.users.get(user_id.value)

    def get_by_email(self, email: str) -> User | None:
        wanted = (email or "").strip().lower()
        for user in self.stores.users.values():
            if user.email.lower() == wanted:
                return user
        return None

    def save(self, user: User) -> None:
        self.stores.users[user.id.value] = user


class InMemoryPersonaRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def get(self, tenant_id: TenantId, persona_id: PersonaId) -> Persona | None:
        p = self.stores.personas.get(persona_id.value)
        if p is None or p.tenant_id != tenant_id:
            return None
        return p

    def list(self, tenant_id: TenantId) -> list[Persona]:
        return [p for p in self.stores.personas.values() if p.tenant_id == tenant_id]

    def save(self, persona: Persona) -> None:
        self.stores.personas[persona.id.value] = persona


class InMemoryMemoryRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def get(self, tenant_id: TenantId, memory_id: MemoryId) -> MemoryItem | None:
        item = self.stores.memories.get(memory_id.value)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def list_active(self, tenant_id: TenantId, persona_id: PersonaId) -> list[MemoryItem]:
        return self.list(tenant_id, persona_id, status=MemoryStatus.ACTIVE)

    def list(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        *,
        memory_type: MemoryType | None = None,
        event_id: EventId | None = None,
        status: MemoryStatus | None = None,
    ) -> list[MemoryItem]:
        items = [
            item
            for item in self.stores.memories.values()
            if item.tenant_id == tenant_id and item.persona_id == persona_id
        ]
        if memory_type is not None:
            items = [item for item in items if item.type is memory_type]
        if event_id is not None:
            items = [item for item in items if item.event_id == event_id]
        if status is not None:
            items = [item for item in items if item.status is status]
        return items

    def save(self, item: MemoryItem) -> None:
        self.stores.memories[item.id.value] = item

    def delete(self, tenant_id: TenantId, memory_id: MemoryId) -> None:
        item = self.get(tenant_id, memory_id)
        if item is None:
            return
        item.status = MemoryStatus.DELETED
        self.stores.vectors.pop(memory_id.value, None)


class InMemoryInboxRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def add(self, item: InboxItem) -> None:
        self.stores.inbox[item.id] = item

    def get(self, tenant_id: TenantId, inbox_id: str) -> InboxItem | None:
        item = self.stores.inbox.get(inbox_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        return item

    def list_pending(self, tenant_id: TenantId, persona_id: PersonaId) -> list[InboxItem]:
        return [
            i
            for i in self.stores.inbox.values()
            if i.tenant_id == tenant_id and i.persona_id == persona_id and i.status == "pending"
        ]

    def save(self, item: InboxItem) -> None:
        self.stores.inbox[item.id] = item


class InMemoryEventGraphRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def save_node(self, node: EventNode) -> None:
        self.stores.events[node.id.value] = node

    def get(self, tenant_id: TenantId, event_id: EventId) -> EventNode | None:
        node = self.stores.events.get(event_id.value)
        if node is None or node.tenant_id != tenant_id:
            return None
        return node

    def list_nodes(self, tenant_id: TenantId, persona_id: PersonaId) -> list[EventNode]:
        return [
            e
            for e in self.stores.events.values()
            if e.tenant_id == tenant_id and e.persona_id == persona_id
        ]

    def add_edge(self, edge: EventEdge) -> None:
        from_n = self.stores.events.get(edge.from_id.value)
        to_n = self.stores.events.get(edge.to_id.value)
        if from_n is None or to_n is None:
            raise DomainError("NOT_FOUND", "event node missing")
        EventEdge.between(from_n, to_n, edge.kind)
        self.stores.edges.append(edge)

    def list_edges(self, tenant_id: TenantId, persona_id: PersonaId) -> list[EventEdge]:
        return [e for e in self.stores.edges if e.tenant_id == tenant_id and e.persona_id == persona_id]


class InMemoryThreadRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def get(self, tenant_id: TenantId, thread_id: ThreadId) -> Thread | None:
        t = self.stores.threads.get(thread_id.value)
        if t is None or t.tenant_id != tenant_id:
            return None
        return t

    def list(self, tenant_id: TenantId, persona_id: PersonaId) -> list[Thread]:
        return sorted(
            (
                t
                for t in self.stores.threads.values()
                if t.tenant_id == tenant_id and t.persona_id == persona_id
            ),
            key=lambda t: t.id.value,
        )

    def save(self, thread: Thread) -> None:
        self.stores.threads[thread.id.value] = thread


class InMemoryVectorIndex:
    def __init__(self, stores: InMemoryStores, memories: InMemoryMemoryRepository) -> None:
        self.stores = stores
        self.memories = memories

    def upsert(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        memory_id: MemoryId,
        vector: list[float],
        status: MemoryStatus,
    ) -> None:
        self.stores.vectors[memory_id.value] = (tenant_id.value, persona_id.value, vector, status)

    def search(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        query_vector: list[float],
        k: int,
        filters: dict | None = None,
    ) -> list[tuple[MemoryItem, float]]:
        if tenant_id is None:
            raise DomainError("VALIDATION_ERROR", "tenant_id required")
        hits: list[tuple[MemoryItem, float]] = []
        for mid, (tid, pid, vec, status) in self.stores.vectors.items():
            if tid != tenant_id.value or pid != persona_id.value:
                continue
            if status is not MemoryStatus.ACTIVE:
                continue
            item = self.memories.get(tenant_id, MemoryId(mid))
            if item is None or not item.is_searchable():
                continue
            if not _apply_inmemory_filters(item, filters):
                continue
            hits.append((item, cosine(query_vector, vec)))
        hits.sort(key=lambda x: x[1], reverse=True)
        return hits[:k]

    def delete(self, tenant_id: TenantId, memory_id: MemoryId) -> None:
        rec = self.stores.vectors.get(memory_id.value)
        if rec and rec[0] == tenant_id.value:
            self.stores.vectors.pop(memory_id.value, None)


def _is_fight_query(text: str) -> bool:
    blob = (text or "").strip()
    if "吵架" in blob:
        return True
    return "为什么" in blob and any(token in blob for token in ("吵", "闹", "生气", "冷战"))


def _pick_fight_citation(injected_memory_ids: list[str]) -> str | None:
    """Demo/suite-v1: episode memory for 面店争吵 event."""
    preferred = "0a000000-0000-4000-a000-000000000303"
    if preferred in injected_memory_ids:
        return preferred
    for mid in injected_memory_ids:
        if mid.endswith("303"):
            return mid
    return None


def _build_scripted_response(text: str, injected_memory_ids: list[str], extra_id: str | None) -> dict:
    citations: list[str] = []
    if _is_fight_query(text):
        fight_id = _pick_fight_citation(injected_memory_ids)
        if fight_id:
            citations.append(fight_id)
            reply = "上次是因为面里放了香菜，你们在杭州老张面馆吵了起来。"
        else:
            reply = "我这边没有找到上次吵架相关的记忆。"
    else:
        if injected_memory_ids:
            citations.append(injected_memory_ids[0])
        if extra_id and extra_id in injected_memory_ids and extra_id not in citations:
            citations.append(extra_id)
        reply = _scripted_reply(text, citations)
    return {"text": reply, "citations": citations}


class ScriptedLLM:
    def __init__(self, extra_citation_memory_id: str | None = None) -> None:
        self.extra_citation_memory_id = extra_citation_memory_id
        self.last_slots: dict | None = None
        self.last_injected: list[str] = []
        self.calls: list[dict] = []

    def complete(self, *, prompt_slots: dict, text: str, injected_memory_ids: list[str]) -> dict:
        self.last_slots = prompt_slots
        self.last_injected = list(injected_memory_ids)
        self.calls.append({"text": text, "slots": prompt_slots, "injected": list(injected_memory_ids)})
        return _build_scripted_response(text, list(injected_memory_ids), self.extra_citation_memory_id)

    def complete_stream(self, *, prompt_slots: dict, text: str, injected_memory_ids: list[str]):
        """Deterministic byte-by-byte stream mirror of :meth:`complete`.

        Yields chunks of the reply text, then a final ``StreamFinished``
        sentinel carrying the same raw envelope ``complete`` would produce.
        """
        self.last_slots = prompt_slots
        self.last_injected = list(injected_memory_ids)
        self.calls.append({"text": text, "slots": prompt_slots, "injected": list(injected_memory_ids)})
        merged = _build_scripted_response(text, list(injected_memory_ids), self.extra_citation_memory_id)
        citations = list(merged.get("citations") or [])
        reply = str(merged.get("text") or "")
        yield from chunk_text(reply)
        raw = json.dumps({"text": reply, "citations": citations}, ensure_ascii=False)
        yield StreamFinished(raw)


class ScriptedReasoner:
    def __init__(
        self,
        proposed_fact: str | None = None,
        *,
        kind: str = "fact",
        conflicts_with: str | None = None,
    ) -> None:
        self.proposed_fact = proposed_fact
        self.kind = kind
        self.conflicts_with = conflicts_with

    def extract(self, text: str, active_memories: list | None = None) -> dict | None:
        if not self.proposed_fact:
            return None
        out: dict = {"kind": self.kind, "text": self.proposed_fact, "source_text": text}
        if self.conflicts_with:
            out["conflicts_with"] = self.conflicts_with
        return out

    def summarize(self, dialogue: str, prior: str = "") -> str | None:
        blob = (dialogue or "").strip().replace("\n", " ")
        if not blob:
            return None
        if len(blob) <= 200:
            return blob
        return blob[:199] + "…"


def _scripted_reply(text: str, citations: list[str]) -> str:
    """Deterministic reply for the scripted LLM that mirrors ``complete``'s
    ``(fake) {text}`` shape so tests asserting the streamed output stay stable."""
    return f"(fake) {text}"


class FixtureEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        if text is None:
            raise DomainError("VALIDATION_ERROR", "text required")
        return fixture_embed(text)


class InMemoryObjectStorage:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def put(self, name: str, data: bytes) -> str:
        self.stores.objects[name] = data
        return name

    def get(self, name: str) -> bytes | None:
        return self.stores.objects.get(name)

    def delete(self, name: str) -> bool:
        if name in self.stores.objects:
            del self.stores.objects[name]
            return True
        return False

    def count(self) -> int:
        return len(self.stores.objects)

    def list_keys(self, prefix: str = "") -> list[str]:
        normalized = (prefix or "").replace("\\", "/").lstrip("/")
        keys = list(self.stores.objects.keys())
        if normalized:
            keys = [key for key in keys if str(key).replace("\\", "/").lstrip("/").startswith(normalized)]
        return sorted(str(key) for key in keys)


class InMemoryAuditLogRepository:
    def __init__(self, stores: InMemoryStores) -> None:
        self.stores = stores

    def append(self, entry: AuditLog) -> None:
        self.stores.audit_logs.append(entry)

    def list(
        self,
        tenant_id: TenantId,
        *,
        action: str | None = None,
        persona_id: PersonaId | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[AuditLog]:
        items = [entry for entry in self.stores.audit_logs if entry.tenant_id == tenant_id]
        if action:
            items = [entry for entry in items if entry.action == action]
        if persona_id is not None:
            items = [entry for entry in items if entry.persona_id == persona_id]
        if since:
            items = [entry for entry in items if (entry.created_at or "") >= since]
        if until:
            items = [entry for entry in items if (entry.created_at or "") <= until]
        return sorted(items, key=lambda entry: (entry.created_at, entry.id), reverse=True)


class FixedClock:
    def now_iso(self) -> str:
        return "2026-08-20T00:00:00+08:00"


class SeqIdGenerator:
    def __init__(self, start: int = 0) -> None:
        self.n = start

    def new_id(self) -> str:
        self.n += 1
        return f"00000000-0000-4000-a000-{self.n:012d}"


class FakeFaithfulnessScorer:
    def score(self, question: str, answer: str, contexts: list[str]) -> float | None:
        return 1.0
