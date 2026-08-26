import pytest

from arbor.adapters.outbound.inmemory import InMemoryMemoryRepository, InMemoryPersonaRepository, InMemoryVectorIndex
from arbor.application.memory.delete_memory import DeleteMemory
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
OLD_CAT = MemoryId("0a000000-0000-4000-a000-000000000307")


def test_delete_memory_requires_admin():
    stores, _send = _stack()
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    delete = DeleteMemory(
        personas=personas,
        memories=memories,
        vectors=vectors,
        auth=AuthorizationPolicy(),
    )
    with pytest.raises(DomainError) as denied:
        delete(
            tenant_id=TENANT,
            user_id=USER,
            persona_id=LINXIA,
            memory_id=OLD_CAT,
            capabilities=[Capability.CHAT, Capability.READ_MEMORY, Capability.WRITE_MEMORY],
        )
    assert denied.value.code == "FORBIDDEN_MEMORY_WRITE"


def test_delete_memory_marks_deleted_and_removes_vectors():
    stores, _send = _stack()
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
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
        memory_id=OLD_CAT,
        capabilities=list(Capability),
    )
    item = memories.get(TENANT, OLD_CAT)
    assert item is not None
    assert item.status.value == "deleted"
    assert OLD_CAT.value not in stores.vectors
