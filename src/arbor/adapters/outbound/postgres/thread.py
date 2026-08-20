from __future__ import annotations

from arbor.adapters.outbound.postgres.mapping import thread_from_row
from arbor.domain.conversation.thread import Citation, Message, Thread
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId


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
        if row is None:
            return None
        thread = thread_from_row(row)
        thread.messages = self._load_messages(tenant_id, thread_id)
        return thread

    def list(self, tenant_id: TenantId, persona_id: PersonaId) -> list[Thread]:
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, summary
            FROM threads
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid
            ORDER BY updated_at DESC, id
            """,
            (tenant_id.value, persona_id.value),
        ).fetchall()
        return [thread_from_row(row) for row in rows]

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
        self.conn.execute(
            "DELETE FROM messages WHERE tenant_id = %s::uuid AND thread_id = %s::uuid",
            (thread.tenant_id.value, thread.id.value),
        )
        for message in thread.messages:
            memory_ids = [c.memory_id.value for c in message.citations if c.memory_id]
            event_ids = [c.event_id.value for c in message.citations if c.event_id]
            self.conn.execute(
                """
                INSERT INTO messages (
                    tenant_id, thread_id, role, content, citation_memory_ids, citation_event_ids
                )
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                """,
                (
                    thread.tenant_id.value,
                    thread.id.value,
                    message.role,
                    message.content,
                    memory_ids,
                    event_ids,
                ),
            )

    def _load_messages(self, tenant_id: TenantId, thread_id: ThreadId) -> list[Message]:
        rows = self.conn.execute(
            """
            SELECT role, content, citation_memory_ids, citation_event_ids
            FROM messages
            WHERE tenant_id = %s::uuid AND thread_id = %s::uuid
            ORDER BY created_at, id
            """,
            (tenant_id.value, thread_id.value),
        ).fetchall()
        messages = []
        for row in rows:
            citations = []
            for mid in row.get("citation_memory_ids") or []:
                citations.append(Citation(memory_id=MemoryId(str(mid))))
            for eid in row.get("citation_event_ids") or []:
                citations.append(Citation(event_id=EventId(str(eid))))
            messages.append(Message(role=row["role"], content=row["content"] or "", citations=citations))
        return messages

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
