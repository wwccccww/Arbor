from arbor.adapters.outbound.inmemory import InMemoryEventGraphRepository, InMemoryStores
from arbor.application.eventgraph.get_tree import GetEventTree
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import load_mini


def test_get_event_tree():
    stores = InMemoryStores()
    load_mini(stores)
    tree = GetEventTree(InMemoryEventGraphRepository(stores))
    linxia = tree(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    zhou = tree(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000020"),
    )
    linxia_ids = {node.id.value for node in linxia["nodes"]}
    zhou_ids = {node.id.value for node in zhou["nodes"]}
    assert "0a000000-0000-4000-a000-000000000102" in linxia_ids
    assert "0a000000-0000-4000-a000-000000000201" not in linxia_ids
    assert zhou_ids == {"0a000000-0000-4000-a000-000000000201"}
