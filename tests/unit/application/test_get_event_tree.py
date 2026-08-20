from arbor.adapters.outbound.inmemory import InMemoryEventGraphRepository, InMemoryMemoryRepository, InMemoryStores
from arbor.application.eventgraph.get_tree import GetEventTree
from arbor.domain.eventgraph.graph import EventNode
from arbor.domain.shared.ids import EventId, PersonaId, TenantId
from tests.unit.application.test_send_message import load_mini


def test_get_event_tree():
    stores = InMemoryStores()
    load_mini(stores)
    tree = GetEventTree(InMemoryEventGraphRepository(stores), memories=InMemoryMemoryRepository(stores))
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
    assert "0a000000-0000-4000-a000-000000000303" in linxia["memory_ids"]["0a000000-0000-4000-a000-000000000102"]


def test_get_event_tree_key_only_hides_daily():
    stores = InMemoryStores()
    load_mini(stores)
    stores.events["daily-1"] = EventNode(
        id=EventId("0a000000-0000-4000-a000-000000000199"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        title="随口一提",
        type="daily",
        importance=3,
    )
    tree = GetEventTree(InMemoryEventGraphRepository(stores))
    all_nodes = tree(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        key_only=False,
    )
    key_nodes = tree(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        key_only=True,
    )
    assert "0a000000-0000-4000-a000-000000000199" in {node.id.value for node in all_nodes["nodes"]}
    assert "0a000000-0000-4000-a000-000000000199" not in {node.id.value for node in key_nodes["nodes"]}
