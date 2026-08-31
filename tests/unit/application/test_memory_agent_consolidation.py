"""Agent episodic inbox → confirm preserves memory_class and supersedes conflicts."""

from __future__ import annotations

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.application.agent.extract_memory import ExtractRunMemory
from arbor.application.memory.commands import ConfirmInboxItem
from arbor.domain.memory.memory import InboxItem, MemoryClass, MemoryStatus
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def test_extract_run_memory_creates_episodic_inbox_candidate():
    stores, _send = _stack()
    from arbor.adapters.outbound.inmemory import InMemoryPersonaRepository

    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    extract = ExtractRunMemory(
        personas=personas,
        inbox=inbox,
        memories=memories,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    added = extract(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        run_id="run-episodic-001",
        goal="登记工单",
        final_output={"text": "工单已登记"},
        tool_results=[{"ticket_id": "t-001"}],
    )
    assert added == 1
    pending = inbox.list_pending(TENANT, LINXIA)
    assert len(pending) == 1
    payload = pending[0].payload
    assert payload.get("memory_class") == "episodic"
    assert payload.get("memory_type") == "episode_summary"


def test_confirm_episodic_inbox_persists_memory_class():
    stores, _send = _stack()
    from arbor.adapters.outbound.inmemory import InMemoryPersonaRepository

    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    inbox.add(
        InboxItem(
            id="agent-episodic-inbox",
            tenant_id=TENANT,
            persona_id=LINXIA,
            kind="fact",
            payload={
                "text": "任务：登记工单；结果：工单已登记",
                "memory_type": "episode_summary",
                "memory_class": "episodic",
                "source_run_id": "run-episodic-002",
            },
        )
    )
    confirm = ConfirmInboxItem(
        personas=personas,
        memories=memories,
        inbox=inbox,
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    new = confirm(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        inbox_id="agent-episodic-inbox",
        capabilities=list(Capability),
    )
    assert new.memory_class == MemoryClass.EPISODIC
    stored = memories.get(TENANT, new.id)
    assert stored is not None
    assert stored.memory_class == MemoryClass.EPISODIC


def test_confirm_agent_conflict_supersedes_prior_episode():
    stores, _send = _stack()
    from arbor.adapters.outbound.inmemory import InMemoryPersonaRepository

    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    old_id = MemoryId("0a000000-0000-4000-a000-000000000302")
    inbox.add(
        InboxItem(
            id="agent-conflict-inbox",
            tenant_id=TENANT,
            persona_id=LINXIA,
            kind="conflict",
            payload={
                "text": "林夏其实可以接受香菜",
                "memory_class": "episodic",
                "memory_type": "episode_summary",
            },
            conflicts_with=old_id,
        )
    )
    confirm = ConfirmInboxItem(
        personas=personas,
        memories=memories,
        inbox=inbox,
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    new = confirm(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        inbox_id="agent-conflict-inbox",
        capabilities=list(Capability),
    )
    old = memories.get(TENANT, old_id)
    assert old is not None
    assert old.status == MemoryStatus.SUPERSEDED
    assert new.supersedes == old_id
