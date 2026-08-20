from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.shared.ids import PersonaId, TenantId, UserId


@dataclass
class AuditLog:
    id: str
    tenant_id: TenantId
    actor_user_id: UserId
    action: str
    resource_type: str = ""
    resource_id: str | None = None
    persona_id: PersonaId | None = None
    payload: dict = field(default_factory=dict)
    created_at: str = ""
