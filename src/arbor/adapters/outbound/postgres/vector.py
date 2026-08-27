from __future__ import annotations

from arbor.adapters.outbound.postgres.lexical import memory_lexical_tokens
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
        clauses = [
            "tenant_id = %s::uuid",
            "persona_id = %s::uuid",
            "status = 'active'",
            "embedding IS NOT NULL",
        ]
        params: list = [query, tenant_id.value, persona_id.value]
        if filters:
            event_ids = filters.get("event_ids")
            if event_ids:
                clauses.append("event_id = ANY(%s::uuid[])")
                params.append([str(value) for value in event_ids])
            types = filters.get("types")
            if types:
                clauses.append("type = ANY(%s::text[])")
                params.append([str(value) for value in types])
            exclude_ids = filters.get("exclude_ids")
            if exclude_ids:
                clauses.append("NOT (id = ANY(%s::uuid[]))")
                params.append([str(value) for value in exclude_ids])
        where_sql = " AND ".join(clauses)
        params.extend([query, k])
        rows = self.conn.execute(
            f"""
            SELECT id, tenant_id, persona_id, text, type, status, event_id, thread_id, supersedes,
                   1 - (embedding <=> %s::vector) AS score
            FROM memory_items
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            tuple(params),
        ).fetchall()
        hits = []
        for row in rows:
            item = memory_from_row(row)
            if not item.is_searchable():
                continue
            hits.append((item, float(row["score"])))
        return hits

    def lexical_search(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        query: str,
        k: int,
        filters: dict | None = None,
    ) -> list[MemoryItem]:
        require_tenant(tenant_id)
        if persona_id is None:
            raise DomainError("VALIDATION_ERROR", "persona_id required")
        tokens = memory_lexical_tokens(query)
        if not tokens:
            return []
        clauses = [
            "tenant_id = %s::uuid",
            "persona_id = %s::uuid",
            "status = 'active'",
            "text_tsv @@ plainto_tsquery('simple', %s)",
        ]
        params: list = [tenant_id.value, persona_id.value, tokens]
        if filters:
            event_ids = filters.get("event_ids")
            if event_ids:
                clauses.append("event_id = ANY(%s::uuid[])")
                params.append([str(value) for value in event_ids])
            types = filters.get("types")
            if types:
                clauses.append("type = ANY(%s::text[])")
                params.append([str(value) for value in types])
            exclude_ids = filters.get("exclude_ids")
            if exclude_ids:
                clauses.append("NOT (id = ANY(%s::uuid[]))")
                params.append([str(value) for value in exclude_ids])
        where_sql = " AND ".join(clauses)
        rank_params = [tokens, tenant_id.value, persona_id.value, tokens]
        rank_params.extend(params[2:])  # filter params after tenant/persona/tokens
        rank_params.append(k)
        rows = self.conn.execute(
            f"""
            SELECT id, tenant_id, persona_id, text, type, status, event_id, thread_id, supersedes,
                   ts_rank_cd(text_tsv, plainto_tsquery('simple', %s)) AS score
            FROM memory_items
            WHERE {where_sql}
            ORDER BY score DESC
            LIMIT %s
            """,
            tuple(rank_params),
        ).fetchall()
        hits: list[MemoryItem] = []
        for row in rows:
            item = memory_from_row(row)
            if item.is_searchable():
                hits.append(item)
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
