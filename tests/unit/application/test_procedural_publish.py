from __future__ import annotations

from arbor.adapters.outbound.inmemory import (
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
)
from arbor.application.agent.employee_templates import DEMO_TENANT, LINXIA_PERSONA_ID
from arbor.application.memory.procedural_commands import PublishProceduralMemory
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import MemoryId, UserId
from arbor.observability.memory import InMemoryObservability


def test_publish_procedural_memory_supersedes_and_metrics():
    stores = InMemoryStores()
    from tests.unit.application.test_send_message import load_mini

    load_mini(stores)
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    persona = personas.get(DEMO_TENANT, LINXIA_PERSONA_ID)
    assert persona is not None
    admin = UserId("0a000000-0000-4000-a000-000000000002")
    persona.grants.append(Grant(user_id=admin, capabilities=[Capability.ADMIN, Capability.CHAT]))
    old = MemoryItem(
        id=MemoryId("proc-old"),
        tenant_id=DEMO_TENANT,
        persona_id=LINXIA_PERSONA_ID,
        text="old SOP",
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.PROCEDURAL,
        source={"published": True, "version": "v2"},
    )
    draft = MemoryItem(
        id=MemoryId("proc-draft"),
        tenant_id=DEMO_TENANT,
        persona_id=LINXIA_PERSONA_ID,
        text="new SOP",
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.PROCEDURAL,
        source={"draft": True, "version": "v2"},
    )
    memories.save(old)
    memories.save(draft)
    obs = InMemoryObservability()
    cmd = PublishProceduralMemory(
        personas=personas,
        memories=memories,
        auth=AuthorizationPolicy(),
        observability=obs,
    )
    result = cmd(
        tenant_id=DEMO_TENANT,
        user_id=admin,
        persona_id=LINXIA_PERSONA_ID,
        memory_id=draft.id,
        workspace_admin=True,
    )
    assert result["published"] is True
    saved_old = memories.get(DEMO_TENANT, old.id)
    saved_draft = memories.get(DEMO_TENANT, draft.id)
    assert saved_old is not None and saved_old.source.get("superseded") is True
    assert saved_draft is not None and saved_draft.source.get("published") is True
    assert any(name == "arbor_procedural_memory_publish_total" for name, _, _ in obs.counters)
