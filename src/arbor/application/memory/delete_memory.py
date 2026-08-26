from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, UserId


class DeleteMemory:
    def __init__(self, *, personas, memories, vectors, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.memories = memories
        self.vectors = vectors
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        memory_id: MemoryId,
        capabilities: list[Capability] | None = None,
    ) -> None:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.ADMIN not in caps:
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "admin required")
        item = self.memories.get(tenant_id, memory_id)
        if item is None or item.persona_id != persona_id:
            raise DomainError("NOT_FOUND", "not found")
        self.memories.delete(tenant_id, memory_id)
        self.vectors.delete(tenant_id, memory_id)
