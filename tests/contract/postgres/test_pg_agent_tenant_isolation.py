"""Contract: agent_runs are tenant-scoped in Postgres."""

from __future__ import annotations

import os

import pytest

from arbor.domain.agent.run import AgentRun, AgentRunStatus
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
def test_agent_run_not_visible_cross_tenant(pg):
    run = AgentRun(
        id="agent-run-tenant-a-001",
        tenant_id=TENANT_A,
        persona_id=LINXIA,
        requested_by=USER,
        goal="租户 A 隔离测试",
        status=AgentRunStatus.PENDING,
        employee_definition_version="1.0",
    )
    pg.agent_runs.save(run)
    assert pg.agent_runs.get(TENANT_A, run.id) is not None
    assert pg.agent_runs.get(TENANT_B, run.id) is None
