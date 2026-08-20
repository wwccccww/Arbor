from __future__ import annotations

from psycopg.types.json import Jsonb

from arbor.domain.audit.log import AuditLog
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def _iso(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def audit_from_row(row: dict) -> AuditLog:
    persona = row.get("persona_id")
    resource = row.get("resource_id")
    return AuditLog(
        id=str(row["id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        actor_user_id=UserId(str(row["actor_user_id"])),
        action=str(row["action"] or ""),
        resource_type=str(row.get("resource_type") or ""),
        resource_id=str(resource) if resource is not None else None,
        persona_id=PersonaId(str(persona)) if persona is not None else None,
        payload=dict(row.get("payload") or {}),
        created_at=_iso(row.get("created_at")),
    )


class PgAuditLogRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def append(self, entry: AuditLog) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_logs (
                id, tenant_id, actor_user_id, action, resource_type, resource_id, persona_id, payload, created_at
            )
            VALUES (
                %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s, COALESCE(%s::timestamptz, now())
            )
            """,
            (
                entry.id,
                entry.tenant_id.value,
                entry.actor_user_id.value,
                entry.action,
                entry.resource_type,
                entry.resource_id,
                entry.persona_id.value if entry.persona_id else None,
                Jsonb(dict(entry.payload or {})),
                entry.created_at or None,
            ),
        )

    def list(
        self,
        tenant_id: TenantId,
        *,
        action: str | None = None,
        persona_id: PersonaId | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[AuditLog]:
        sql = [
            """
            SELECT id, tenant_id, actor_user_id, action, resource_type, resource_id, persona_id, payload, created_at
            FROM audit_logs
            WHERE tenant_id = %s::uuid
            """
        ]
        params: list = [tenant_id.value]
        if action:
            sql.append("AND action = %s")
            params.append(action)
        if persona_id is not None:
            sql.append("AND persona_id = %s::uuid")
            params.append(persona_id.value)
        if since:
            sql.append("AND created_at >= %s::timestamptz")
            params.append(since)
        if until:
            sql.append("AND created_at <= %s::timestamptz")
            params.append(until)
        sql.append("ORDER BY created_at DESC, id DESC")
        rows = self.conn.execute("\n".join(sql), params).fetchall()
        return [audit_from_row(row) for row in rows]
