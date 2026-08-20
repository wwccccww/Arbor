from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, UserId


class ConfirmInboxItem:
    def __init__(self, *, personas, memories, inbox, vectors, embed, ids, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.memories = memories
        self.inbox = inbox
        self.vectors = vectors
        self.embed = embed
        self.ids = ids
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        inbox_id: str | None = None,
        capabilities: list[Capability] | None = None,
    ) -> MemoryItem:
        persona = self.personas.get(tenant_id, persona_id)
        caps = capabilities or (self.auth.capabilities_for(persona, user_id) if persona else [])
        if Capability.WRITE_MEMORY not in caps and not (persona and self.auth.can_write_memory(persona, user_id)):
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")
        pending = self.inbox.list_pending(tenant_id, persona_id)
        if not pending:
            raise DomainError("NOT_FOUND", "no pending inbox")
        item = next((p for p in pending if inbox_id is None or p.id == inbox_id), pending[0])
        old = None
        if item.conflicts_with:
            old = self.memories.get(tenant_id, item.conflicts_with)
        new_id = MemoryId(self.ids.new_id())
        new_mem = MemoryItem(
            id=new_id,
            tenant_id=tenant_id,
            persona_id=persona_id,
            text=item.payload.get("text", ""),
            type=MemoryType.FACT,
            status=MemoryStatus.ACTIVE,
        )
        item.confirm(new_mem, old)
        self.memories.save(new_mem)
        if old:
            self.memories.save(old)
            self.vectors.delete(tenant_id, old.id)
        self.inbox.save(item)
        self.vectors.upsert(tenant_id, persona_id, new_mem.id, self.embed.embed(new_mem.text), new_mem.status)
        return new_mem


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
    def __init__(self, *, personas, storage, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.storage = storage
        self.auth = auth

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
