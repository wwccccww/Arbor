from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId


class ListAuditLogs:
    def __init__(self, logs) -> None:
        self.logs = logs

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        workspace_admin: bool,
        action: str | None = None,
        persona_id: PersonaId | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        return self.logs.list(
            tenant_id,
            action=action,
            persona_id=persona_id,
            since=since,
            until=until,
        )
