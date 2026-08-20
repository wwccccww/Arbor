from __future__ import annotations

from dataclasses import dataclass

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import EventId, PersonaId, TenantId


@dataclass
class EventNode:
    id: EventId
    tenant_id: TenantId
    persona_id: PersonaId
    title: str
    summary: str = ""
    type: str = "daily"
    importance: int = 3
    happened_at: str | None = None


@dataclass
class EventEdge:
    from_id: EventId
    to_id: EventId
    kind: str
    tenant_id: TenantId
    persona_id: PersonaId

    @classmethod
    def between(cls, from_event: EventNode, to_event: EventNode, kind: str) -> EventEdge:
        if from_event.tenant_id != to_event.tenant_id or from_event.persona_id != to_event.persona_id:
            raise DomainError("EVENT_EDGE_PERSONA_MISMATCH", "event edge must stay in one persona")
        return cls(
            from_id=from_event.id,
            to_id=to_event.id,
            kind=kind,
            tenant_id=from_event.tenant_id,
            persona_id=from_event.persona_id,
        )
