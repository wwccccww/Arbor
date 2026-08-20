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
