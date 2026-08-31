from __future__ import annotations

from arbor.domain.agent.run import AgentRun
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def test_agent_run_budget_exhausted():
    run = AgentRun(
        id="run-1",
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        requested_by=UserId("0a000000-0000-4000-a000-000000000002"),
        goal="test",
        current_step=8,
        max_steps=8,
    )
    assert run.budget_exhausted()


def test_planner_action_validation_rejects_unknown():
    from arbor.domain.agent.action import validate_planner_action

    try:
        validate_planner_action({"action": "fly"})
    except DomainError as exc:
        assert exc.code == "VALIDATION_ERROR"
    else:
        raise AssertionError("expected validation error")
