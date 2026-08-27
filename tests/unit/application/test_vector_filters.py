from __future__ import annotations

from arbor.adapters.outbound.inmemory import (
    InMemoryMemoryRepository,
    InMemoryStores,
    InMemoryVectorIndex,
)
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")


def test_vector_search_event_id_filter():
    stores = InMemoryStores()
    memories = InMemoryMemoryRepository(stores)
    index = InMemoryVectorIndex(stores, memories)
    event_a = "0a000000-0000-4000-a000-000000000101"
    event_b = "0a000000-0000-4000-a000-000000000102"
    from arbor.domain.shared.ids import EventId

    item_a = MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000301"),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text="面店吵架细节",
        type=MemoryType.EPISODE_SUMMARY,
        status=MemoryStatus.ACTIVE,
        event_id=EventId(event_a),
    )
    item_b = MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000302"),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text="其他事件细节",
        type=MemoryType.EPISODE_SUMMARY,
        status=MemoryStatus.ACTIVE,
        event_id=EventId(event_b),
    )
    stores.memories[item_a.id.value] = item_a
    stores.memories[item_b.id.value] = item_b
    vec = fixture_embed("面店吵架细节")
    index.upsert(TENANT, PERSONA, item_a.id, vec, item_a.status)
    index.upsert(TENANT, PERSONA, item_b.id, vec, item_b.status)

    hits = index.search(
        tenant_id=TENANT,
        persona_id=PERSONA,
        query_vector=vec,
        k=5,
        filters={"event_ids": [event_a]},
    )
    assert len(hits) == 1
    assert hits[0][0].id.value == item_a.id.value
