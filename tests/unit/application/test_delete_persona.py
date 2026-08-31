from __future__ import annotations

import pytest

from arbor.adapters.outbound.inmemory import InMemoryPersonaRepository, InMemoryStores
from arbor.application.agent.employee_templates import (
    DEMO_TENANT,
    LINXIA_PERSONA_ID,
    InMemoryEmployeeDefinitions,
)
from arbor.application.persona.delete_persona import DeletePersona
from arbor.domain.agent.employee import DigitalEmployeeDefinition, EmployeeReleaseStatus
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import PersonaId, UserId

ADMIN = UserId("0a000000-0000-4000-a000-000000000002")


def test_delete_persona_archives_employee_definitions():
    stores = InMemoryStores()
    personas = InMemoryPersonaRepository(stores)
    pid = PersonaId("0a000000-0000-4000-a000-000000000099")
    personas.save(
        Persona(
            id=pid,
            tenant_id=DEMO_TENANT,
            skin="companion",
            profile=Profile(display_name="待删除"),
            grants=[Grant(user_id=ADMIN, capabilities=[Capability.ADMIN, Capability.CHAT])],
        )
    )
    employees = InMemoryEmployeeDefinitions()
    employees.create_draft(
        DEMO_TENANT,
        DigitalEmployeeDefinition(
            tenant_id=DEMO_TENANT,
            persona_id=pid,
            version="1.0",
            role="test",
            release_status=EmployeeReleaseStatus.PUBLISHED,
            eval_gate_passed=True,
        ),
    )
    cmd = DeletePersona(
        personas=personas,
        employee_definitions=employees,
        auth=AuthorizationPolicy(),
    )
    result = cmd(
        tenant_id=DEMO_TENANT,
        user_id=ADMIN,
        persona_id=pid,
        workspace_admin=True,
    )
    assert result["deleted"] is True
    assert result["employee_definitions_archived"] == 1
    assert personas.get(DEMO_TENANT, pid) is None
    archived = employees.get(DEMO_TENANT, pid, "1.0")
    assert archived is not None
    assert archived.release_status == EmployeeReleaseStatus.ARCHIVED


def test_plan_script_blocked_without_env(monkeypatch):
    monkeypatch.delenv("ARBOR_ALLOW_PLAN_SCRIPT", raising=False)
    from arbor.adapters.inbound.agent_eval_stack import build_agent_eval_stack
    from arbor.application.agent.start_run import StartAgentRun

    stack = build_agent_eval_stack(use_employee_templates=False)
    start = StartAgentRun(
        personas=stack["personas"],
        runs=stack["runs"],
        auth=stack["approve_step"].auth,
        ids=stack["approve_step"].advance.ids,
    )
    with pytest.raises(DomainError) as exc:
        start(
            tenant_id=DEMO_TENANT,
            user_id=ADMIN,
            persona_id=LINXIA_PERSONA_ID,
            goal="test",
            plan_script=[{"schema_version": 1, "action": "answer", "text": "x", "completion": True}],
            enqueue=False,
        )
    assert exc.value.code == "FORBIDDEN_PLAN_SCRIPT"
