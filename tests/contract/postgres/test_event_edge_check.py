import pytest

from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge
from arbor.domain.shared.ids import EventId, PersonaId, TenantId


def test_event_edge_check(pg):
    with pytest.raises(DomainError) as exc:
        pg.events.add_edge(
            EventEdge(
                from_id=EventId("0a000000-0000-4000-a000-000000000102"),
                to_id=EventId("0a000000-0000-4000-a000-000000000201"),
                kind="temporal",
                tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
                persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            )
        )
    assert exc.value.code == "EVENT_EDGE_PERSONA_MISMATCH"
