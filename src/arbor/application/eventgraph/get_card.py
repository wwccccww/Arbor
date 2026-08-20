from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import EventId, TenantId, UserId

ATTACHMENT_TYPES = frozenset(
    {MemoryType.FILE_CHUNK, MemoryType.IMAGE_CAPTION, MemoryType.TRANSCRIPT}
)


class GetEventCard:
    def __init__(self, *, events, memories, personas, auth: AuthorizationPolicy) -> None:
        self.events = events
        self.memories = memories
        self.personas = personas
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        event_id: EventId,
        capabilities: list[Capability] | None = None,
    ) -> dict:
        node = self.events.get(tenant_id, event_id)
        if node is None:
            raise DomainError("NOT_FOUND", "not found")
        persona = self.personas.get(tenant_id, node.persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.READ_MEMORY not in caps:
            raise DomainError("NOT_FOUND", "not found")
        related = self.memories.list(
            tenant_id,
            node.persona_id,
            event_id=node.id,
            status=MemoryStatus.ACTIVE,
        )
        attachments = [item for item in related if item.type in ATTACHMENT_TYPES]
        memories = [item for item in related if item.type not in ATTACHMENT_TYPES]
        return {"node": node, "memories": memories, "attachments": attachments}
