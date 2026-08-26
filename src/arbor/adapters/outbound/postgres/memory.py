from __future__ import annotations

from psycopg.types.json import Jsonb

from arbor.adapters.outbound.postgres.mapping import memory_from_row
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId


class PgMemoryRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, tenant_id: TenantId, memory_id: MemoryId) -> MemoryItem | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, text, type, status, event_id, thread_id, supersedes, source
            FROM memory_items
            WHERE id = %s::uuid AND tenant_id = %s::uuid
            """,
            (memory_id.value, tenant_id.value),
        ).fetchone()
        return memory_from_row(row) if row else None

    def list_active(self, tenant_id: TenantId, persona_id: PersonaId) -> list[MemoryItem]:
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, text, type, status, event_id, thread_id, supersedes, source
            FROM memory_items
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND status = 'active'
            """,
            (tenant_id.value, persona_id.value),
        ).fetchall()
        return [memory_from_row(row) for row in rows]

    def list(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        *,
        memory_type: MemoryType | None = None,
        event_id: EventId | None = None,
        status: MemoryStatus | None = None,
    ) -> list[MemoryItem]:
        sql = [
            """
            SELECT id, tenant_id, persona_id, text, type, status, event_id, thread_id, supersedes, source
            FROM memory_items
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            """
        ]
        params: list = [tenant_id.value, persona_id.value]
        if memory_type is not None:
            sql.append("AND type = %s")
            params.append(memory_type.value)
        if event_id is not None:
            sql.append("AND event_id = %s::uuid")
            params.append(event_id.value)
        if status is not None:
            sql.append("AND status = %s")
            params.append(status.value)
        sql.append("ORDER BY id")
        rows = self.conn.execute("\n".join(sql), params).fetchall()
        return [memory_from_row(row) for row in rows]

    def save(self, item: MemoryItem) -> None:
        self.conn.execute(
            """
            INSERT INTO memory_items (
                id, tenant_id, persona_id, thread_id, event_id, type, text, status, supersedes, source
            )
            VALUES (
                %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                text = EXCLUDED.text,
                type = EXCLUDED.type,
                status = EXCLUDED.status,
                event_id = EXCLUDED.event_id,
                thread_id = EXCLUDED.thread_id,
                supersedes = EXCLUDED.supersedes,
                source = EXCLUDED.source
            """,
            (
                item.id.value,
                item.tenant_id.value,
                item.persona_id.value,
                item.thread_id.value if item.thread_id else None,
                item.event_id.value if item.event_id else None,
                item.type.value,
                item.text,
                item.status.value,
                item.supersedes.value if item.supersedes else None,
                Jsonb(item.source) if item.source else None,
            ),
        )

    def delete(self, tenant_id: TenantId, memory_id: MemoryId) -> None:
        self.conn.execute(
            """
            UPDATE memory_items
            SET status = 'deleted', embedding = NULL
            WHERE id = %s::uuid AND tenant_id = %s::uuid
            """,
            (memory_id.value, tenant_id.value),
        )
