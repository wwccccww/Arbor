from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header, Query

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId


@dataclass
class AuditHttpDeps:
    list_audit_logs: Callable
    current_user: Callable
    workspace_admin_for: Callable


def register_audit_routes(app, deps: AuditHttpDeps) -> None:
    @app.get("/v1/audit-logs")
    def get_audit_logs(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
        action: str | None = Query(default=None),
        persona_id: str | None = Query(default=None),
        since: str | None = Query(default=None),
        until: str | None = Query(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        items = deps.list_audit_logs(
            tenant_id=TenantId(x_tenant_id),
            workspace_admin=deps.workspace_admin_for(user, x_tenant_id),
            action=action,
            persona_id=PersonaId(persona_id) if persona_id else None,
            since=since,
            until=until,
        )
        return {
            "items": [
                {
                    "id": entry.id,
                    "actor_user_id": entry.actor_user_id.value,
                    "action": entry.action,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "persona_id": entry.persona_id.value if entry.persona_id else None,
                    "payload": entry.payload,
                    "created_at": entry.created_at,
                }
                for entry in items
            ]
        }
