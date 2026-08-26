from __future__ import annotations

from dataclasses import dataclass

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import EventId, PersonaId, TenantId

KEY_EVENT_TYPES = frozenset({"milestone", "promise", "conflict"})
KEY_EVENT_IMPORTANCE = 4
EDGE_KINDS = frozenset({"temporal", "caused_by", "involves_person"})


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
    confidence: float | None = None

    def is_key(self) -> bool:
        return self.importance >= KEY_EVENT_IMPORTANCE or self.type in KEY_EVENT_TYPES


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
        if kind not in EDGE_KINDS:
            raise DomainError("VALIDATION_ERROR", f"unknown edge kind {kind}")
        return cls(
            from_id=from_event.id,
            to_id=to_event.id,
            kind=kind,
            tenant_id=from_event.tenant_id,
            persona_id=from_event.persona_id,
        )


class EventTreeProjector:
    """Read-only projection. Key events come from importance/type, not vector similarity."""

    def project(
        self,
        nodes: list[EventNode],
        edges: list[EventEdge],
        *,
        view: str = "tree",
        key_only: bool = False,
    ) -> tuple[list[EventNode], list[EventEdge]]:
        if view not in {"tree", "timeline"}:
            raise DomainError("VALIDATION_ERROR", "view must be tree or timeline")
        selected = [node for node in nodes if not key_only or node.is_key()]
        ids = {node.id.value for node in selected}
        selected_edges = [
            edge for edge in edges if edge.from_id.value in ids and edge.to_id.value in ids
        ]
        if view == "timeline":
            selected = sorted(selected, key=lambda node: node.happened_at or "")
        return selected, selected_edges
