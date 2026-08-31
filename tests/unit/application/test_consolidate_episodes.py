from __future__ import annotations

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.application.memory.consolidate_episodes import ConsolidateEpisodicMemories
from arbor.application.memory.consolidation import is_consolidation
from arbor.domain.memory.memory import MemoryClass, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _episodic(memory_id: str, text: str) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(memory_id),
        tenant_id=TENANT,
        persona_id=LINXIA,
        text=text,
        type=MemoryType.EPISODE_SUMMARY,
        status=MemoryStatus.ACTIVE,
        memory_class=MemoryClass.EPISODIC,
    )


def test_consolidate_episodes_merges_similar_memories():
    stores, _send = _stack()
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    memories.save(_episodic("ep-001", "林夏讨厌香菜"))
    memories.save(_episodic("ep-002", "林夏不喜欢香菜"))
    for item in memories.list_active(TENANT, LINXIA):
        vectors.upsert(TENANT, LINXIA, item.id, [0.1, 0.2], item.status)

    consolidate = ConsolidateEpisodicMemories(
        personas=personas,
        memories=memories,
        vectors=vectors,
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    result = consolidate(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
    )
    assert result["group_count"] == 1
    assert len(result["created_consolidation_ids"]) == 1
    consolidations = [m for m in memories.list_active(TENANT, LINXIA) if is_consolidation(m)]
    assert len(consolidations) == 1
    assert consolidations[0].source and consolidations[0].source.get("consolidation")
    assert len(consolidations[0].source.get("derived_from") or []) == 2
    superseded = memories.get(TENANT, MemoryId("ep-001"))
    assert superseded is not None
    assert superseded.status == MemoryStatus.SUPERSEDED


def test_delete_source_removes_derived_consolidation():
    stores, _send = _stack()
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    memories.save(_episodic("ep-010", "林夏讨厌香菜"))
    memories.save(_episodic("ep-011", "林夏不喜欢香菜"))
    for item in memories.list_active(TENANT, LINXIA):
        vectors.upsert(TENANT, LINXIA, item.id, [0.1, 0.2], item.status)

    consolidate = ConsolidateEpisodicMemories(
        personas=personas,
        memories=memories,
        vectors=vectors,
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    consolidate(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
    )
    from arbor.application.memory.delete_memory import DeleteMemory

    delete = DeleteMemory(
        personas=personas,
        memories=memories,
        vectors=vectors,
        auth=AuthorizationPolicy(),
    )
    delete(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        memory_id=MemoryId("ep-010"),
        capabilities=list(Capability),
    )
    assert not [m for m in memories.list_active(TENANT, LINXIA) if is_consolidation(m)]
    remaining = memories.get(TENANT, MemoryId("ep-011"))
    assert remaining is not None
    assert remaining.status == MemoryStatus.SUPERSEDED

