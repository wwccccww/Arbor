
from arbor.application.retrieval import rerank_memories
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _mem(text: str, mid: str) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(mid),
        tenant_id=TENANT,
        persona_id=PERSONA,
        text=text,
        type=MemoryType.FACT,
        status=MemoryStatus.ACTIVE,
    )


def test_rerank_orders_by_query_overlap():
    a = _mem("林夏讨厌香菜", "0a000000-0000-4000-a000-000000000301")
    b = _mem("西湖区租房信息", "0a000000-0000-4000-a000-000000000302")
    ranked = rerank_memories("讨厌香菜", [b, a], fixture_embed, limit=2)
    assert [item.id.value for item in ranked] == [a.id.value, b.id.value]
