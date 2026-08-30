from __future__ import annotations

from psycopg.types.json import Jsonb

from arbor.adapters.outbound.postgres.mapping import inbox_from_row
from arbor.domain.memory.memory import InboxItem
from arbor.domain.shared.ids import PersonaId, TenantId


class PgInboxRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def add(self, item: InboxItem) -> None:
        self.save(item)

    def get(self, tenant_id: TenantId, inbox_id: str) -> InboxItem | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, kind, payload, conflict_with, status, created_at
            FROM inbox_items
            WHERE id = %s AND tenant_id = %s::uuid
            """,
            (inbox_id, tenant_id.value),
        ).fetchone()
        return inbox_from_row(row) if row else None

    def list_pending(self, tenant_id: TenantId, persona_id: PersonaId) -> list[InboxItem]:
        rows = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, kind, payload, conflict_with, status, created_at
            FROM inbox_items
            WHERE tenant_id = %s::uuid AND persona_id = %s::uuid AND status = 'pending'
            """,
            (tenant_id.value, persona_id.value),
        ).fetchall()
        return [inbox_from_row(row) for row in rows]

    def count_pending(self, tenant_id: TenantId | None = None) -> int:
        if tenant_id is None:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM inbox_items WHERE status = 'pending'"
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT COUNT(*) AS n FROM inbox_items
                WHERE tenant_id = %s::uuid AND status = 'pending'
                """,
                (tenant_id.value,),
            ).fetchone()
        return int(row["n"] if row else 0)

    def save(self, item: InboxItem) -> None:
        self.conn.execute(
            """
            INSERT INTO inbox_items (
                id, tenant_id, persona_id, kind, payload, conflict_with, status
            )
            VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                payload = EXCLUDED.payload,
                conflict_with = EXCLUDED.conflict_with,
                status = EXCLUDED.status
            """,
            (
                item.id,
                item.tenant_id.value,
                item.persona_id.value,
                item.kind,
                Jsonb(item.payload),
                item.conflicts_with.value if item.conflicts_with else None,
                item.status,
            ),
        )
