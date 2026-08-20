from __future__ import annotations

from arbor.adapters.outbound.postgres.mapping import thread_from_row
from arbor.domain.conversation.thread import Thread
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId


class PgThreadRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, tenant_id: TenantId, thread_id: ThreadId) -> Thread | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, summary
            FROM threads
            WHERE id = %s::uuid AND tenant_id = %s::uuid
            """,
            (thread_id.value, tenant_id.value),
        ).fetchone()
        return thread_from_row(row) if row else None

    def save(self, thread: Thread) -> None:
        self.conn.execute(
            """
            INSERT INTO threads (id, tenant_id, persona_id, summary, updated_at)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, now())
            ON CONFLICT (id) DO UPDATE SET
                summary = EXCLUDED.summary,
                updated_at = now()
            """,
            (thread.id.value, thread.tenant_id.value, thread.persona_id.value, thread.summary),
        )

    def summary_for(self, persona_id: PersonaId) -> str:
        row = self.conn.execute(
            """
            SELECT summary FROM threads
            WHERE persona_id = %s::uuid
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (persona_id.value,),
        ).fetchone()
        return row["summary"] if row else ""

    def get_by_persona(self, tenant_id: TenantId, persona_id: PersonaId) -> Thread | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, summary
            FROM threads
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            LIMIT 1
            """,
            (tenant_id.value, persona_id.value),
        ).fetchone()
        return thread_from_row(row) if row else None
