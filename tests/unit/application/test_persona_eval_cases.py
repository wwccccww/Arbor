from arbor.application.evaluation.persona_cases import build_persona_eval_cases
from arbor.domain.eventgraph.graph import EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
ZHOU = PersonaId("0a000000-0000-4000-a000-000000000020")
USER = "0a000000-0000-4000-a000-000000000099"


def test_build_persona_eval_cases_from_facts_and_events():
    memories = [
        MemoryItem(
            id=MemoryId("0a000000-0000-4000-a000-000000000301"),
            tenant_id=TENANT,
            persona_id=LINXIA,
            text="林夏讨厌香菜",
            type=MemoryType.FACT,
            status=MemoryStatus.ACTIVE,
        ),
        MemoryItem(
            id=MemoryId("0a000000-0000-4000-a000-000000000401"),
            tenant_id=TENANT,
            persona_id=ZHOU,
            text="小周负责工单",
            type=MemoryType.FACT,
            status=MemoryStatus.ACTIVE,
        ),
    ]
    events = [
        EventNode(
            id=EventId("0a000000-0000-4000-a000-000000000102"),
            tenant_id=TENANT,
            persona_id=LINXIA,
            title="面店争吵",
            type="conflict",
            importance=5,
            happened_at="2024-11-02",
        ),
    ]
    cases = build_persona_eval_cases(
        tenant_id=TENANT,
        persona_id=LINXIA,
        user_id=USER,
        memories=memories,
        events=events,
        limit=8,
    )
    assert cases
    assert all(case["actor"]["persona_id"] == LINXIA.value for case in cases)
    assert any("香菜" in case["query"] for case in cases)
    assert any(case.get("expected_event_id") for case in cases)
    forbidden_union = set()
    for case in cases:
        forbidden_union.update(case.get("forbidden_memory_ids") or [])
    assert "0a000000-0000-4000-a000-000000000401" in forbidden_union
