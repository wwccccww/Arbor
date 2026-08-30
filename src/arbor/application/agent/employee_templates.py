from __future__ import annotations

from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.shared.ids import PersonaId

LINXIA_PERSONA_ID = PersonaId("0a000000-0000-4000-a000-000000000010")


class InMemoryEmployeeDefinitions:
    def __init__(self) -> None:
        self._by_persona: dict[str, dict[str, DigitalEmployeeDefinition]] = {}

    def register(self, definition: DigitalEmployeeDefinition) -> None:
        bucket = self._by_persona.setdefault(definition.persona_id.value, {})
        bucket[definition.version] = definition

    def get(self, persona_id: PersonaId, version: str | None = None) -> DigitalEmployeeDefinition | None:
        bucket = self._by_persona.get(persona_id.value) or {}
        if version:
            return bucket.get(version)
        published = [
            d for d in bucket.values() if d.release_status == EmployeeReleaseStatus.PUBLISHED
        ]
        if not published:
            return bucket.get("1.0")
        return max(published, key=lambda d: d.version)


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
        )
    )
    store.register(
        DigitalEmployeeDefinition(
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
        )
    )
    return store
