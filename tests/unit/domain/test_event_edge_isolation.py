import pytest

from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.shared.ids import EventId, PersonaId, TenantId


def test_event_edge_isolation():
    a = EventNode(
        id=EventId("0a000000-0000-4000-a000-000000000102"),
        tenant_id=TenantId("t"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        title="面店争吵",
    )
    b = EventNode(
        id=EventId("0a000000-0000-4000-a000-000000000201"),
        tenant_id=TenantId("t"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000020"),
        title="工单",
    )
    with pytest.raises(DomainError) as exc:
        EventEdge.between(a, b, "temporal")
    assert exc.value.code == "EVENT_EDGE_PERSONA_MISMATCH"


def test_key_event_uses_importance_and_type():
    daily = EventNode(
        id=EventId("0a000000-0000-4000-a000-000000000199"),
        tenant_id=TenantId("t"),
        persona_id=PersonaId("p"),
        title="随口一提",
    )
    milestone = EventNode(
        id=EventId("0a000000-0000-4000-a000-000000000101"),
        tenant_id=TenantId("t"),
        persona_id=PersonaId("p"),
        title="第一次见面",
        type="milestone",
        importance=3,
    )
    work = EventNode(
        id=EventId("0a000000-0000-4000-a000-000000000201"),
        tenant_id=TenantId("t"),
        persona_id=PersonaId("p"),
        title="工单升级",
        type="work",
        importance=4,
    )
    assert daily.is_key() is False
    assert milestone.is_key() is True
    assert work.is_key() is True
