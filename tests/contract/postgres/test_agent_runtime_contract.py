"""Contract: agent_runs / agent_steps persistence and tenant scope."""

from __future__ import annotations

import os

import pytest

from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.agent.step import AgentStep, StepKind, StepStatus
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT_A = TenantId("0a000000-0000-4000-a000-000000000001")
TENANT_B = TenantId("0b000000-0000-4000-b000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_agent_step_persisted_and_tenant_scoped(pg):
    run = AgentRun(
        id="agent-run-steps-001",
        tenant_id=TENANT_A,
        persona_id=LINXIA,
        requested_by=USER,
        goal="步骤持久化契约",
        status=AgentRunStatus.RUNNING,
        employee_definition_version="1.0",
        metadata={"metrics": {"total_latency_ms": 42.5, "step_count": 1}},
        consumed_cost_micros=50_000,
    )
    pg.agent_runs.save(run)
    step = AgentStep(
        id="agent-step-001",
        run_id=run.id,
        tenant_id=TENANT_A,
        persona_id=LINXIA,
        sequence=1,
        kind=StepKind.RETRIEVE,
        status=StepStatus.COMPLETED,
        output={"hit_ids": ["m1"]},
        observation={"latency_ms": 42.5},
    )
    pg.agent_steps.add(step)

    listed = pg.agent_steps.list_for_run(TENANT_A, run.id)
    assert len(listed) == 1
    assert listed[0].observation.get("latency_ms") == 42.5
    assert pg.agent_steps.get(TENANT_B, step.id) is None

    saved = pg.agent_runs.get(TENANT_A, run.id)
    assert saved is not None
    assert saved.consumed_cost_micros == 50_000
    assert saved.metadata.get("metrics", {}).get("total_latency_ms") == 42.5
