from __future__ import annotations

from arbor.application.audit.commands import RecordAudit
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class DeletePersona:
    """Delete persona and archive all employee definitions for that persona."""

    def __init__(
        self,
        *,
        personas,
        employee_definitions=None,
        auth: AuthorizationPolicy,
        audit: RecordAudit | None = None,
    ) -> None:
        self.personas = personas
        self.employee_definitions = employee_definitions
        self.auth = auth
        self.audit = audit

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        workspace_admin: bool = False,
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.ADMIN not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        archived = 0
        if self.employee_definitions is not None and hasattr(
            self.employee_definitions, "archive_all_for_persona"
        ):
            archived = self.employee_definitions.archive_all_for_persona(tenant_id, persona_id)
        if not self.personas.delete(tenant_id, persona_id):
            raise DomainError("NOT_FOUND", "persona not found")
        if self.audit is not None:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                action="persona.delete",
                resource_type="persona",
                resource_id=persona_id.value,
                persona_id=persona_id,
                payload={"employee_definitions_archived": archived},
            )
        return {"deleted": True, "employee_definitions_archived": archived}
