from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


class GetEmployeeDefinition:
    def __init__(self, *, personas, employee_definitions, auth: AuthorizationPolicy) -> None:
        self.personas = personas
        self.employee_definitions = employee_definitions
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        version: str | None = None,
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        definition = self.employee_definitions.get(persona_id, version=version)
        if definition is None:
            raise DomainError("NOT_FOUND", "employee definition not found")
        return {
            "persona_id": definition.persona_id.value,
            "version": definition.version,
            "role": definition.role,
            "goals": list(definition.goals),
            "skills": list(definition.skills),
            "knowledge_scopes": list(definition.knowledge_scopes),
            "tool_policy": dict(definition.tool_policy),
            "approval_policy": dict(definition.approval_policy),
            "memory_policy": dict(definition.memory_policy),
            "escalation_policy": dict(definition.escalation_policy),
            "run_budget_policy": dict(definition.run_budget_policy),
            "evaluation_suite": definition.evaluation_suite,
            "release_status": definition.release_status.value,
        }


class ListEmployeeTemplates:
    def __init__(self, *, employee_definitions) -> None:
        self.employee_definitions = employee_definitions

    def __call__(self) -> dict:
        store = self.employee_definitions
        if hasattr(store, "_by_persona"):
            items = []
            for bucket in store._by_persona.values():
                for definition in bucket.values():
                    items.append(
                        {
                            "persona_id": definition.persona_id.value,
                            "version": definition.version,
                            "role": definition.role,
                            "release_status": definition.release_status.value,
                        }
                    )
            return {"items": items}
        return {"items": []}
