from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from arbor.domain.agent.action import validate_planner_action
from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

CASES = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "examples/agent.yaml").read_text(encoding="utf-8")
)

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def _base_run(**overrides) -> AgentRun:
    payload = {
        "id": "run-gwt-001",
        "tenant_id": TENANT,
        "persona_id": LINXIA,
        "requested_by": USER,
        "goal": "GWT",
        "current_step": 0,
        "max_steps": 8,
        "status": AgentRunStatus.PENDING,
    }
    payload.update(overrides)
    if isinstance(payload.get("status"), str):
        payload["status"] = AgentRunStatus(payload["status"])
    return AgentRun(**payload)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_agent_examples(case):
    action = case["when"]["action"]
    then = case["then"]
    if then.get("error"):
        with pytest.raises(DomainError) as exc:
            _run(case, action)
        assert exc.value.code == then["error"]
        return
    result = _run(case, action)
    if "budget_exhausted" in then:
        assert result == then["budget_exhausted"]
    if "can_advance" in then:
        assert result == then["can_advance"]


def _run(case, action):
    given_run = (case.get("given") or {}).get("run") or {}
    run = _base_run(**given_run)
    if action == "budget_exhausted":
        return run.budget_exhausted()
    if action == "mark_running":
        run.mark_running()
        return None
    if action == "can_advance":
        return run.can_advance()
    if action == "validate_planner_action":
        validate_planner_action(case["when"]["payload"])
        return None
    raise AssertionError(action)
