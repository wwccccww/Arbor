from __future__ import annotations

from arbor.domain.shared.ids import TenantId, UserId


class ListPersonas:
    def __init__(self, personas) -> None:
        self.personas = personas

    def __call__(self, *, tenant_id: TenantId, user_id: UserId, workspace_admin: bool) -> list:
        items = self.personas.list(tenant_id)
        if workspace_admin:
            return items
        return [
            persona
            for persona in items
            if any(grant.user_id == user_id for grant in persona.grants)
        ]
