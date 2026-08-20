from __future__ import annotations

from arbor.domain.audit.log import AuditLog
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class RecordAudit:
    def __init__(self, *, logs, ids, clock) -> None:
        self.logs = logs
        self.ids = ids
        self.clock = clock

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        actor_user_id: UserId,
        action: str,
        resource_type: str = "",
        resource_id: str | None = None,
        persona_id: PersonaId | None = None,
        payload: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            id=self.ids.new_id(),
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            persona_id=persona_id,
            payload=dict(payload or {}),
            created_at=self.clock.now_iso(),
        )
        self.logs.append(entry)
        return entry
