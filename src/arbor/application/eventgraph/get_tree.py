from __future__ import annotations

from arbor.domain.shared.ids import PersonaId, TenantId


class GetEventTree:
    def __init__(self, events) -> None:
        self.events = events

    def __call__(self, *, tenant_id: TenantId, persona_id: PersonaId) -> dict:
        return {
            "nodes": self.events.list_nodes(tenant_id, persona_id),
            "edges": self.events.list_edges(tenant_id, persona_id),
        }
