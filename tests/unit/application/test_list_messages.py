import pytest

from arbor.adapters.outbound.inmemory import InMemoryPersonaRepository, InMemoryThreadRepository
from arbor.application.conversation.threads import ListMessages
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
THREAD = ThreadId("0a000000-0000-4000-a000-000000000030")


def test_list_messages_pages_and_hides_without_chat():
    stores, send = _stack()
    send(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        persona_id=LINXIA,
        text="还在吗",
        capabilities=list(Capability),
    )
    query = ListMessages(
        personas=InMemoryPersonaRepository(stores),
        threads=InMemoryThreadRepository(stores),
        auth=AuthorizationPolicy(),
    )
    with pytest.raises(DomainError) as hidden:
        query(
            tenant_id=TENANT,
            user_id=USER,
            thread_id=THREAD,
            capabilities=[Capability.READ_MEMORY],
        )
    assert hidden.value.code == "NOT_FOUND"
    full = query(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        capabilities=list(Capability),
    )
    assert full.total == 2
    assert [item.role for item in full.items] == ["user", "assistant"]
    paged = query(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        capabilities=list(Capability),
        limit=1,
        offset=0,
    )
    assert len(paged.items) == 1
    assert paged.total == 2
    assert paged.items[0].role == "user"
    rest = query(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        capabilities=list(Capability),
        limit=1,
        offset=1,
    )
    assert [item.role for item in rest.items] == ["assistant"]
    assert rest.total == 2
