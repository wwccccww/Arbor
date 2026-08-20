import pytest

from arbor.adapters.outbound.inmemory import InMemoryMemoryRepository, InMemoryPersonaRepository
from arbor.application.memory.queries import ListMemories
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
FIGHT = "0a000000-0000-4000-a000-000000000102"
CAT_OLD = "0a000000-0000-4000-a000-000000000307"


def test_list_memories_requires_read_and_filters():
    stores, _send = _stack()
    query = ListMemories(
        personas=InMemoryPersonaRepository(stores),
        memories=InMemoryMemoryRepository(stores),
        auth=AuthorizationPolicy(),
    )
    with pytest.raises(DomainError) as hidden:
        query(
            tenant_id=TENANT,
            user_id=USER,
            persona_id=LINXIA,
            capabilities=[Capability.CHAT],
        )
    assert hidden.value.code == "NOT_FOUND"
    active = query(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
    )
    assert all(item.status.value == "active" for item in active)
    assert all(item.id.value != CAT_OLD for item in active)
    by_event = query(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
        event_id=FIGHT,
    )
    assert [item.id.value for item in by_event] == ["0a000000-0000-4000-a000-000000000303"]
    superseded = query(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
        status="superseded",
    )
    assert [item.id.value for item in superseded] == [CAT_OLD]
