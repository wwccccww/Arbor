from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, UserId


class ConfirmInboxItem:
    def __init__(
        self,
        *,
        personas,
        memories,
        inbox,
        vectors,
        embed,
        ids,
        auth: AuthorizationPolicy,
        events=None,
        audit=None,
    ) -> None:
        self.personas = personas
        self.memories = memories
        self.inbox = inbox
        self.vectors = vectors
        self.embed = embed
        self.ids = ids
        self.auth = auth
        self.events = events
        self.audit = audit

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        inbox_id: str | None = None,
        capabilities: list[Capability] | None = None,
        mark_key_event: bool = False,
    ) -> MemoryItem:
        persona = self.personas.get(tenant_id, persona_id)
        caps = capabilities or (self.auth.capabilities_for(persona, user_id) if persona else [])
        if Capability.WRITE_MEMORY not in caps and not (persona and self.auth.can_write_memory(persona, user_id)):
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")
        if inbox_id is None:
            pending = self.inbox.list_pending(tenant_id, persona_id)
            if not pending:
                raise DomainError("NOT_FOUND", "no pending inbox")
            item = pending[0]
        else:
            item = self.inbox.get(tenant_id, inbox_id)
            if item is None or item.persona_id != persona_id:
                raise DomainError("NOT_FOUND", "no pending inbox")
        old = None
        if item.conflicts_with:
            old = self.memories.get(tenant_id, item.conflicts_with)
        text = item.payload.get("text", "")
        memory_type_raw = item.payload.get("memory_type") or "fact"
        try:
            mem_type = MemoryType(memory_type_raw)
        except ValueError:
            mem_type = MemoryType.FACT
        event_id = self._maybe_key_event(tenant_id, persona_id, text) if mark_key_event else None
        new_mem = MemoryItem(
            id=MemoryId(self.ids.new_id()),
            tenant_id=tenant_id,
            persona_id=persona_id,
            text=text,
            type=mem_type,
            status=MemoryStatus.ACTIVE,
            event_id=event_id,
        )
        item.confirm(new_mem, old)
        self.memories.save(new_mem)
        if old:
            self.memories.save(old)
            self.vectors.delete(tenant_id, old.id)
        self.inbox.save(item)
        self.vectors.upsert(tenant_id, persona_id, new_mem.id, self.embed.embed(new_mem.text), new_mem.status)
        if self.audit:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                action="memory.confirm",
                resource_type="memory",
                resource_id=new_mem.id.value,
                persona_id=persona_id,
                payload={"inbox_id": item.id},
            )
        return new_mem

    def _maybe_key_event(self, tenant_id: TenantId, persona_id: PersonaId, text: str) -> EventId:
        if self.events is None:
            raise DomainError("VALIDATION_ERROR", "event graph required")
        previous = self.events.list_nodes(tenant_id, persona_id)
        node = EventNode(
            id=EventId(self.ids.new_id()),
            tenant_id=tenant_id,
            persona_id=persona_id,
            title=(text or "关键事件")[:80],
            summary=text,
            type="milestone",
            importance=5,
        )
        self.events.save_node(node)
        if previous:
            latest = max(previous, key=lambda event: (event.happened_at or "", event.id.value))
            self.events.add_edge(EventEdge.between(latest, node, "temporal"))
        return node.id


class DismissInboxItem:
    def __init__(self, *, personas, inbox, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.inbox = inbox
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        inbox_id: str,
        capabilities: list[Capability] | None = None,
    ) -> None:
        persona = self.personas.get(tenant_id, persona_id)
        caps = capabilities or (self.auth.capabilities_for(persona, user_id) if persona else [])
        if Capability.WRITE_MEMORY not in caps and not (persona and self.auth.can_write_memory(persona, user_id)):
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")
        item = self.inbox.get(tenant_id, inbox_id)
        if item is None or item.persona_id != persona_id:
            raise DomainError("NOT_FOUND", "no pending inbox")
        item.dismiss()
        self.inbox.save(item)


class ImportArtifact:
    def __init__(self, *, personas, storage, auth: AuthorizationPolicy, audit=None) -> None:
        self.personas = personas
        self.storage = storage
        self.auth = auth
        self.audit = audit

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        filename: str,
        data: bytes = b"",
        capabilities: list[Capability] | None = None,
    ) -> None:
        persona = self.personas.get(tenant_id, persona_id)
        caps = capabilities or (self.auth.capabilities_for(persona, user_id) if persona else [])
        if Capability.WRITE_MEMORY not in caps:
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")
        self.storage.put(filename, data)
        if self.audit:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                action="memory.import",
                resource_type="import",
                resource_id=None,
                persona_id=persona_id,
                payload={"filename": filename},
            )


