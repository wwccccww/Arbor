from __future__ import annotations

from arbor.adapters.outbound.inmemory_agent import InMemoryAgentRunRepository, InMemoryAgentStores
from arbor.domain.agent.run import AgentRun, AgentRunStatus
from arbor.domain.shared.ids import PersonaId, TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
USER = UserId("0a000000-0000-4000-a000-000000000002")


def test_try_advance_version_rejects_stale_expected_version():
    stores = InMemoryAgentStores()
    runs = InMemoryAgentRunRepository(stores)
    run = AgentRun(
        id="run-version-001",
        tenant_id=TENANT,
        persona_id=LINXIA,
        requested_by=USER,
        goal="并发推进测试",
        status=AgentRunStatus.RUNNING,
        version=2,
    )
    runs.save(run)
    assert runs.try_advance_version(TENANT, run.id, 2) is True
    assert runs.try_advance_version(TENANT, run.id, 2) is False
    saved = runs.get(TENANT, run.id)
    assert saved is not None
    assert saved.version == 3
