from __future__ import annotations

from arbor.domain.eventgraph.graph import EventTreeProjector
from arbor.domain.shared.ids import PersonaId, TenantId


class GetEventTree:
    def __init__(self, events, memories=None) -> None:
        self.events = events
        self.memories = memories
        self.projector = EventTreeProjector()

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        persona_id: PersonaId,
        view: str = "tree",
        key_only: bool = False,
    ) -> dict:
        api_view = "timeline" if view == "biography" else view
        nodes, edges = self.projector.project(
            self.events.list_nodes(tenant_id, persona_id),
            self.events.list_edges(tenant_id, persona_id),
            view=api_view,
            key_only=key_only,
        )
        memory_ids: dict[str, list[str]] = {}
        if self.memories is not None:
            for item in self.memories.list_active(tenant_id, persona_id):
                if item.event_id:
                    memory_ids.setdefault(item.event_id.value, []).append(item.id.value)
        return {"nodes": nodes, "edges": edges, "memory_ids": memory_ids}
