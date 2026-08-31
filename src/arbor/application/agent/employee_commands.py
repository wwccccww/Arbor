from __future__ import annotations

from arbor.application.audit.commands import RecordAudit
from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def _policy_snapshot(definition: DigitalEmployeeDefinition) -> dict:
    return {
        "version": definition.version,
        "role": definition.role,
        "tool_policy": dict(definition.tool_policy),
        "approval_policy": dict(definition.approval_policy),
        "memory_policy": dict(definition.memory_policy),
        "escalation_policy": dict(definition.escalation_policy),
        "run_budget_policy": dict(definition.run_budget_policy),
        "evaluation_suite": definition.evaluation_suite,
    }


class CreateEmployeeDefinitionDraft:
    def __init__(
        self,
        *,
        personas,
        employee_definitions,
        auth: AuthorizationPolicy,
    ) -> None:
        self.personas = personas
        self.employee_definitions = employee_definitions
        self.auth = auth

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        version: str,
        role: str,
        goals: list[str] | None = None,
        skills: list[str] | None = None,
        knowledge_scopes: list[str] | None = None,
        tool_policy: dict | None = None,
        approval_policy: dict | None = None,
        memory_policy: dict | None = None,
        escalation_policy: dict | None = None,
        run_budget_policy: dict | None = None,
        evaluation_suite: str = "agent-v1",
        workspace_admin: bool = False,
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        version_text = (version or "").strip()
        if not version_text:
            raise DomainError("VALIDATION_ERROR", "version required")
        definition = DigitalEmployeeDefinition(
            tenant_id=tenant_id,
            persona_id=persona_id,
            version=version_text,
            role=(role or "").strip() or "employee",
            goals=list(goals or []),
            skills=list(skills or []),
            knowledge_scopes=list(knowledge_scopes or []),
            tool_policy=dict(tool_policy or {}),
            approval_policy=dict(approval_policy or {}),
            memory_policy=dict(memory_policy or {}),
            escalation_policy=dict(escalation_policy or {}),
            run_budget_policy=dict(run_budget_policy or {}),
            evaluation_suite=evaluation_suite or "agent-v1",
            release_status=EmployeeReleaseStatus.DRAFT,
        )
        saved = self.employee_definitions.create_draft(tenant_id, definition)
        return {
            "persona_id": saved.persona_id.value,
            "version": saved.version,
            "role": saved.role,
            "release_status": saved.release_status.value,
            "evaluation_suite": saved.evaluation_suite,
        }


class PublishEmployeeDefinition:
    def __init__(
        self,
        *,
        personas,
        employee_definitions,
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
        version: str,
        workspace_admin: bool = False,
    ) -> dict:
        if not workspace_admin:
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        published = self.employee_definitions.publish(tenant_id, persona_id, version)
        if self.audit is not None:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                persona_id=persona_id,
                action="employee_definition.publish",
                resource_type="employee_definition",
                resource_id=f"{persona_id.value}:{version}",
                payload={"version": version, "policy_snapshot": _policy_snapshot(published)},
            )
        return {
            "persona_id": published.persona_id.value,
            "version": published.version,
            "release_status": published.release_status.value,
            "eval_gate_passed": published.eval_gate_passed,
        }


class ListEmployeeDefinitionVersions:
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
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        if persona is None:
            raise DomainError("NOT_FOUND", "persona not found")
        if Capability.CHAT not in self.auth.capabilities_for(persona, user_id):
            raise DomainError("FORBIDDEN_CHAT", "chat required")
        items = self.employee_definitions.list_versions(tenant_id, persona_id)
        return {
            "items": [
                {
                    "persona_id": item.persona_id.value,
                    "version": item.version,
                    "role": item.role,
                    "release_status": item.release_status.value,
                    "eval_gate_passed": item.eval_gate_passed,
                    "evaluation_suite": item.evaluation_suite,
                }
                for item in items
            ]
        }
