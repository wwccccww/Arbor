from __future__ import annotations

import psycopg.errors

from arbor.adapters.outbound.postgres.mapping import edge_from_row, event_from_row
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.shared.ids import EventId, PersonaId, TenantId


class PgEventGraphRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def save_node(self, node: EventNode) -> None:
        self.conn.execute(
            """
            INSERT INTO event_nodes (
                id, tenant_id, persona_id, title, happened_at, type, importance, summary
            )
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                happened_at = EXCLUDED.happened_at,
                type = EXCLUDED.type,
                importance = EXCLUDED.importance,
                summary = EXCLUDED.summary
            """,
            (
                node.id.value,
                node.tenant_id.value,
                node.persona_id.value,
                node.title,
                node.happened_at,
                node.type,
                node.importance,
                node.summary,
            ),
        )

    def _node(self, event_id: EventId) -> EventNode | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, title, happened_at, type, importance, summary
            FROM event_nodes
            WHERE id = %s::uuid
            """,
            (event_id.value,),
        ).fetchone()
        return event_from_row(row) if row else None

    def list_nodes(self, tenant_id: TenantId, persona_id: PersonaId) -> list[EventNode]:
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, title, happened_at, type, importance, summary
            FROM event_nodes
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            """,
            (tenant_id.value, persona_id.value),
        ).fetchall()
        return [event_from_row(row) for row in rows]

    def add_edge(self, edge: EventEdge) -> None:
        from_n = self._node(edge.from_id)
        to_n = self._node(edge.to_id)
        if from_n is None or to_n is None:
            raise DomainError("NOT_FOUND", "event node missing")
        EventEdge.between(from_n, to_n, edge.kind)
        try:
            self.conn.execute(
                """
                INSERT INTO event_edges (tenant_id, persona_id, from_id, to_id, kind)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s)
                """,
                (
                    from_n.tenant_id.value,
                    from_n.persona_id.value,
                    edge.from_id.value,
                    edge.to_id.value,
                    edge.kind,
                ),
            )
        except psycopg.errors.CheckViolation as exc:
            raise DomainError("EVENT_EDGE_PERSONA_MISMATCH", "event edge must stay in one persona") from exc

    def list_edges(self, tenant_id: TenantId, persona_id: PersonaId) -> list[EventEdge]:
        rows = self.conn.execute(
            """
            SELECT from_id, to_id, kind, tenant_id, persona_id
            FROM event_edges
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            """,
            (tenant_id.value, persona_id.value),
        ).fetchall()
        return [edge_from_row(row) for row in rows]
