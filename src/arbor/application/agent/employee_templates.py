from __future__ import annotations

from copy import deepcopy

from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId

LINXIA_PERSONA_ID = PersonaId("0a000000-0000-4000-a000-000000000010")
DEMO_TENANT = TenantId("0a000000-0000-4000-a000-000000000001")


def _key(tenant_id: TenantId | None, persona_id: PersonaId, version: str) -> tuple[str, str, str]:
    return (tenant_id.value if tenant_id else "", persona_id.value, version)


class InMemoryEmployeeDefinitions:
    """Test adapter implementing EmployeeDefinitionRepository."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], DigitalEmployeeDefinition] = {}

    def register(self, definition: DigitalEmployeeDefinition) -> None:
        self._items[_key(definition.tenant_id, definition.persona_id, definition.version)] = definition

    def create_draft(
        self,
        tenant_id: TenantId,
        definition: DigitalEmployeeDefinition,
    ) -> DigitalEmployeeDefinition:
        draft = deepcopy(definition)
        draft.tenant_id = tenant_id
        draft.release_status = EmployeeReleaseStatus.DRAFT
        draft.eval_gate_passed = False
        if self.get(tenant_id, draft.persona_id, draft.version) is not None:
            raise DomainError("CONFLICT", "employee definition version already exists")
        self.register(draft)
        return draft

    def get(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str | None = None,
    ) -> DigitalEmployeeDefinition | None:
        if version:
            exact = self._items.get(_key(tenant_id, persona_id, version))
            if exact is not None:
                return exact
            return self._items.get(_key(None, persona_id, version))
        scoped = [
            d
            for k, d in self._items.items()
            if k[1] == persona_id.value and (k[0] == tenant_id.value or k[0] == "")
        ]
        if not scoped:
            return None
        published = [d for d in scoped if d.release_status == EmployeeReleaseStatus.PUBLISHED]
        if published:
            return max(published, key=lambda d: d.version)
        return max(scoped, key=lambda d: d.version)

    def list_versions(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
    ) -> list[DigitalEmployeeDefinition]:
        items = [
            d
            for k, d in self._items.items()
            if k[1] == persona_id.value and (k[0] == tenant_id.value or k[0] == "")
        ]
        return sorted(items, key=lambda d: d.version, reverse=True)

    def record_eval_gate(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
        *,
        gate_passed: bool,
        report: dict | None = None,
    ) -> None:
        definition = self.get(tenant_id, persona_id, version)
        if definition is None:
            raise DomainError("NOT_FOUND", "employee definition not found")
        definition.eval_gate_passed = gate_passed
        if report:
            definition.memory_policy.setdefault("_eval_report", report)

    def publish(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
    ) -> DigitalEmployeeDefinition:
        definition = self.get(tenant_id, persona_id, version)
        if definition is None:
            raise DomainError("NOT_FOUND", "employee definition not found")
        if definition.release_status == EmployeeReleaseStatus.PUBLISHED:
            raise DomainError("VALIDATION_ERROR", "already published")
        if not definition.eval_gate_passed:
            raise DomainError("EMPLOYEE_EVAL_GATE", "employee eval gate not passed")
        for item in self.list_versions(tenant_id, persona_id):
            if (
                item.version != version
                and item.release_status == EmployeeReleaseStatus.PUBLISHED
            ):
                item.release_status = EmployeeReleaseStatus.ARCHIVED
        definition.release_status = EmployeeReleaseStatus.PUBLISHED
        return definition

    def archive(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
        version: str,
    ) -> DigitalEmployeeDefinition:
        definition = self.get(tenant_id, persona_id, version)
        if definition is None:
            raise DomainError("NOT_FOUND", "employee definition not found")
        definition.release_status = EmployeeReleaseStatus.ARCHIVED
        return definition

    def archive_all_for_persona(
        self,
        tenant_id: TenantId,
        persona_id: PersonaId,
    ) -> int:
        archived = 0
        for item in self.list_versions(tenant_id, persona_id):
            if item.release_status != EmployeeReleaseStatus.ARCHIVED:
                item.release_status = EmployeeReleaseStatus.ARCHIVED
                archived += 1
        return archived


def default_employee_templates() -> InMemoryEmployeeDefinitions:
    store = InMemoryEmployeeDefinitions()
    store.register(
        DigitalEmployeeDefinition(
            persona_id=PersonaId("template-customer-service"),
            version="1.0",
            role="customer_service",
            goals=["resolve incidents", "create tickets when needed"],
            skills=["policy_lookup", "ticket.create", "calendar.list"],
            knowledge_scopes=["semantic_memory", "procedural_memory", "episodic_memory"],
            tool_policy={"allowed_tools": ["calendar", "ticket"]},
            approval_policy={"ticket.create": True},
            escalation_policy={"evidence_insufficient": "handoff_human", "user_escalation": "handoff_human"},
            run_budget_policy={"max_steps": 8, "token_budget": 16000},
            evaluation_suite="agent-v1",
            eval_gate_passed=True,
        )
    )
    store.register(
        DigitalEmployeeDefinition(
            persona_id=PersonaId("template-tutor"),
            version="1.0",
            role="enterprise_tutor",
            goals=["guide learning", "track progress"],
            skills=["knowledge_lookup"],
            knowledge_scopes=["semantic_memory", "episodic_memory"],
            tool_policy={"allowed_tools": []},
            approval_policy={},
            memory_policy={"auto_write": False},
            escalation_policy={"high_risk_action": "deny"},
            run_budget_policy={"max_steps": 6, "token_budget": 12000},
            evaluation_suite="agent-v1",
            eval_gate_passed=True,
        )
    )
    store.register(
        DigitalEmployeeDefinition(
            persona_id=PersonaId("template-interviewer"),
            version="1.0",
            role="interviewer",
            goals=["structured interview", "evidence capture"],
            skills=["question_generation"],
            knowledge_scopes=["semantic_memory"],
            tool_policy={"allowed_tools": []},
            approval_policy={"final_decision": True},
            escalation_policy={"final_decision": "human_required"},
            run_budget_policy={"max_steps": 6, "token_budget": 12000},
            evaluation_suite="agent-v1",
            eval_gate_passed=True,
        )
    )
    store.register(
        DigitalEmployeeDefinition(
            tenant_id=DEMO_TENANT,
            persona_id=LINXIA_PERSONA_ID,
            version="1.0",
            role="customer_service",
            goals=["resolve incidents", "create tickets when needed"],
            skills=["policy_lookup", "ticket.create", "calendar.list"],
            knowledge_scopes=["semantic_memory", "procedural_memory", "episodic_memory"],
            tool_policy={"allowed_tools": ["calendar", "ticket"]},
            approval_policy={"ticket.create": True},
            escalation_policy={"evidence_insufficient": "handoff_human", "user_escalation": "handoff_human"},
            run_budget_policy={"max_steps": 8, "token_budget": 16000},
            evaluation_suite="agent-v1",
            eval_gate_passed=True,
        )
    )
    return store
