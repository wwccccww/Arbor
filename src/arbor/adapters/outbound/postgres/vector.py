from __future__ import annotations

from arbor.adapters.outbound.postgres.mapping import memory_from_row
from arbor.adapters.outbound.postgres.sql import require_tenant, vector_literal
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import MemoryItem, MemoryStatus
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId


class PgVectorIndex:
    def __init__(self, conn, memories) -> None:
        self.conn = conn
        self.memories = memories

    def upsert(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        memory_id: MemoryId,
        vector: list[float],
        status: MemoryStatus,
    ) -> None:
        require_tenant(tenant_id)
        self.conn.execute(
            """
            UPDATE memory_items
            SET embedding = %s::vector, status = %s
            WHERE id = %s::uuid AND tenant_id = %s::uuid AND persona_id = %s::uuid
            """,
            (
                vector_literal(vector),
                status.value,
                memory_id.value,
                tenant_id.value,
                persona_id.value,
            ),
        )

    def search(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        query_vector: list[float],
        k: int,
        filters: dict | None = None,
    ) -> list[tuple[MemoryItem, float]]:
        require_tenant(tenant_id)
        if persona_id is None:
            raise DomainError("VALIDATION_ERROR", "persona_id required")
        query = vector_literal(query_vector)
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, text, type, status, event_id, thread_id, supersedes,
                   1 - (embedding <=> %s::vector) AS score
            FROM memory_items
            WHERE tenant_id = %s::uuid
              AND persona_id = %s::uuid
              AND status = 'active'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query, tenant_id.value, persona_id.value, query, k),
        ).fetchall()
        hits = []
        for row in rows:
            item = memory_from_row(row)
            if not item.is_searchable():
                continue
            hits.append((item, float(row["score"])))
        return hits

    def delete(self, tenant_id: TenantId, memory_id: MemoryId) -> None:
        require_tenant(tenant_id)
        self.conn.execute(
            """
            UPDATE memory_items
            SET embedding = NULL
            WHERE id = %s::uuid AND tenant_id = %s::uuid
            """,
            (memory_id.value, tenant_id.value),
        )
