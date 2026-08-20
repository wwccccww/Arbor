from arbor.adapters.outbound.inmemory import (
    InMemoryEventGraphRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
)
from arbor.application.eventgraph.get_card import GetEventCard
from arbor.application.eventgraph.get_tree import GetEventTree
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId
from tests.unit.application.test_send_message import USER, load_mini


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


def test_get_event_card_tenant_and_read_memory():
    stores = InMemoryStores()
    load_mini(stores)
    card = GetEventCard(
        events=InMemoryEventGraphRepository(stores),
        memories=InMemoryMemoryRepository(stores),
        personas=InMemoryPersonaRepository(stores),
        auth=AuthorizationPolicy(),
    )
    found = card(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        event_id=EventId("0a000000-0000-4000-a000-000000000102"),
        capabilities=list(Capability),
    )
    assert found["node"].title == "面店争吵"
    assert any(item.id.value == "0a000000-0000-4000-a000-000000000303" for item in found["memories"])
    assert found["attachments"] == []
    meet_id = EventId("0a000000-0000-4000-a000-000000000101")
    caption_id = MemoryId("0a000000-0000-4000-a000-000000000306")
    stores.events[meet_id.value] = EventNode(
        id=meet_id,
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        title="第一次见面",
    )
    stores.memories[caption_id.value] = MemoryItem(
        id=caption_id,
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text="照片：西湖边第一次见面",
        type=MemoryType.IMAGE_CAPTION,
        event_id=meet_id,
    )
    meet = card(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        event_id=meet_id,
        capabilities=list(Capability),
    )
    assert [item.id.value for item in meet["attachments"]] == ["0a000000-0000-4000-a000-000000000306"]
    assert all(item.type.value == "image_caption" for item in meet["attachments"])
    assert all(item.id.value != "0a000000-0000-4000-a000-000000000306" for item in meet["memories"])
    try:
        card(
            tenant_id=TenantId("0b000000-0000-4000-a000-000000000001"),
            user_id=USER,
            event_id=EventId("0a000000-0000-4000-a000-000000000102"),
            capabilities=list(Capability),
        )
        raise AssertionError("expected NOT_FOUND")
    except DomainError as exc:
        assert exc.code == "NOT_FOUND"
