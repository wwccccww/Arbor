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
        verbatim = [item for item in memories if item.type in {MemoryType.EPISODE_SUMMARY, MemoryType.TRANSCRIPT}]
        facts = [item for item in memories if item not in verbatim]

        all_nodes = self.events.list_nodes(tenant_id, node.persona_id)
        node_by_id = {n.id.value: n for n in all_nodes}
        all_edges = self.events.list_edges(tenant_id, node.persona_id)

        causal_out = []
        causal_in = []
        participants: list[str] = []
        for edge in all_edges:
            if edge.from_id == node.id and edge.kind == "caused_by":
                target = node_by_id.get(edge.to_id.value)
                causal_out.append(
                    {
                        "event_id": edge.to_id.value,
                        "title": target.title if target else edge.to_id.value,
                        "kind": edge.kind,
                    }
                )
            if edge.to_id == node.id and edge.kind == "caused_by":
                source = node_by_id.get(edge.from_id.value)
                causal_in.append(
                    {
                        "event_id": edge.from_id.value,
                        "title": source.title if source else edge.from_id.value,
                        "kind": edge.kind,
                    }
                )
            if edge.from_id == node.id and edge.kind == "involves_person":
                target = node_by_id.get(edge.to_id.value)
                label = target.title if target else edge.to_id.value
                if label not in participants:
                    participants.append(label)
            if edge.to_id == node.id and edge.kind == "involves_person":
                source = node_by_id.get(edge.from_id.value)
                label = source.title if source else edge.from_id.value
                if label not in participants:
                    participants.append(label)

        return {
            "node": node,
            "memories": facts,
            "verbatim": verbatim,
            "attachments": attachments,
            "causal_out": causal_out,
            "causal_in": causal_in,
            "participants": participants,
        }
