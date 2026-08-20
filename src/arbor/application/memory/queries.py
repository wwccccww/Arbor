from __future__ import annotations

from dataclasses import dataclass

from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import EventId, PersonaId, TenantId, UserId


@dataclass(frozen=True)
class MemoryPage:
    items: list
    total: int


class ListMemories:
    def __init__(self, *, personas, memories, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.memories = memories
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        capabilities: list[Capability] | None = None,
        memory_type: str | None = None,
        event_id: str | None = None,
        status: str | None = "active",
        limit: int = 50,
        offset: int = 0,
    ) -> MemoryPage:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "not found")
        caps = capabilities or self.auth.capabilities_for(persona, user_id)
        if Capability.READ_MEMORY not in caps:
            raise DomainError("NOT_FOUND", "not found")
        parsed_type = _parse_type(memory_type)
        parsed_status = _parse_status(status)
        parsed_event = EventId(event_id) if event_id else None
        if limit < 1 or limit > 100:
            raise DomainError("VALIDATION_ERROR", "limit must be 1..100")
        if offset < 0:
            raise DomainError("VALIDATION_ERROR", "offset must be >= 0")
        items = self.memories.list(
            tenant_id,
            persona_id,
            memory_type=parsed_type,
            event_id=parsed_event,
            status=parsed_status,
        )
        return MemoryPage(items=items[offset : offset + limit], total=len(items))


def _parse_type(raw: str | None) -> MemoryType | None:
    if not raw:
        return None
    try:
        return MemoryType(raw)
    except ValueError as exc:
        raise DomainError("VALIDATION_ERROR", "unknown memory type") from exc


def _parse_status(raw: str | None) -> MemoryStatus | None:
    if raw is None or raw == "":
        return MemoryStatus.ACTIVE
    try:
        return MemoryStatus(raw)
    except ValueError as exc:
        raise DomainError("VALIDATION_ERROR", "unknown memory status") from exc
