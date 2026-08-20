import inspect

import pytest

from arbor.adapters.outbound.inmemory import (
    InMemoryEventGraphRepository,
    InMemoryMemoryRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    fixture_embed,
)
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId
from tests.unit.application.test_send_message import load_mini


def _make_index():
    stores = InMemoryStores()
    load_mini(stores)
    memories = InMemoryMemoryRepository(stores)
    return stores, memories, InMemoryVectorIndex(stores, memories)


def test_memory_tenant_filter():
    _stores, _memories, index = _make_index()
    hits = index.search(
        tenant_id=TenantId("0b000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0b000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("林夏讨厌香菜，点餐不能放香菜。"),
        k=5,
    )
    assert all(h[0].id.value != "0a000000-0000-4000-a000-000000000302" for h in hits)


def test_vector_search_isolation():
    _stores, memories, index = _make_index()
    cat = index.search(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("林夏喜欢猫想养宠物"),
        k=5,
    )
    assert all(h[0].id.value != "0a000000-0000-4000-a000-000000000307" for h in cat)

    sig = inspect.signature(index.search)
    assert sig.parameters["tenant_id"].default is inspect.Parameter.empty
    with pytest.raises(DomainError) as missing:
        index.search(
            tenant_id=None,  # type: ignore[arg-type]
            persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            query_vector=[0.0],
            k=5,
        )
    assert missing.value.code == "VALIDATION_ERROR"

    mid = MemoryId("0a000000-0000-4000-a000-000000000305")
    memories.delete(TenantId("0a000000-0000-4000-a000-000000000001"), mid)
    after = index.search(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        query_vector=fixture_embed("每周日晚上打电话"),
        k=5,
    )
    assert all(h[0].id != mid for h in after)


def test_event_edge_check():
    stores, _memories, _index = _make_index()
    events = InMemoryEventGraphRepository(stores)
    with pytest.raises(DomainError) as exc:
        events.add_edge(
            EventEdge(
                from_id=EventId("0a000000-0000-4000-a000-000000000102"),
                to_id=EventId("0a000000-0000-4000-a000-000000000201"),
                kind="temporal",
                tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
                persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            )
        )
    assert exc.value.code == "EVENT_EDGE_PERSONA_MISMATCH"
