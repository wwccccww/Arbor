import pytest

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.application.memory.commands import ConfirmInboxItem, DismissInboxItem
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import InboxItem
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack, test_confirm_inbox_makes_searchable


def test_confirm_inbox():
    test_confirm_inbox_makes_searchable()


def _pending_item(stores, text: str, inbox_id: str) -> InboxItem:
    item = InboxItem(
        id=inbox_id,
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        kind="fact",
        payload={"text": text},
    )
    InMemoryInboxRepository(stores).add(item)
    return item


def test_confirm_missing_inbox_id_does_not_confirm_another():
    stores, _send = _stack()
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    _pending_item(stores, "该留着", "keep-me")
    confirm = ConfirmInboxItem(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        inbox=inbox,
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    with pytest.raises(DomainError) as exc:
        confirm(
            tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
            user_id=USER,
            persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            inbox_id="missing-id",
            capabilities=list(Capability),
        )
    assert exc.value.code == "NOT_FOUND"
    pending = inbox.list_pending(
        TenantId("0a000000-0000-4000-a000-000000000001"),
        PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    assert [item.id for item in pending] == ["keep-me"]


def test_confirm_non_pending_inbox_is_conflict():
    stores, _send = _stack()
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    _pending_item(stores, "只能确认一次", "once-me")
    confirm = ConfirmInboxItem(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        inbox=inbox,
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    kwargs = dict(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        inbox_id="once-me",
        capabilities=list(Capability),
    )
    confirm(**kwargs)
    with pytest.raises(DomainError) as exc:
        confirm(**kwargs)
    assert exc.value.code == "CONFLICT_INBOX_STATE"


def test_dismiss_inbox_item():
    stores, _send = _stack()
    inbox = InMemoryInboxRepository(stores)
    _pending_item(stores, "可忽略", "drop-me")
    dismiss = DismissInboxItem(
        personas=InMemoryPersonaRepository(stores),
        inbox=inbox,
        auth=AuthorizationPolicy(),
    )
    dismiss(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        inbox_id="drop-me",
        capabilities=list(Capability),
    )
    pending = inbox.list_pending(
        TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    assert pending == []
    assert inbox.get(TenantId("0a000000-0000-4000-a000-000000000001"), "drop-me").status == "dismissed"


def test_confirm_mark_key_event_grows_tree():
    stores, _send = _stack()
    memories = InMemoryMemoryRepository(stores)
    events = InMemoryEventGraphRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    _pending_item(stores, "和好后去了西湖", "key-1")
    confirm = ConfirmInboxItem(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        inbox=inbox,
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        events=events,
    )
    before = {node.id.value for node in events.list_nodes(
        TenantId("0a000000-0000-4000-a000-000000000001"),
        PersonaId("0a000000-0000-4000-a000-000000000010"),
    )}
    memory = confirm(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        inbox_id="key-1",
        capabilities=list(Capability),
        mark_key_event=True,
    )
    assert memory.event_id is not None
    after = events.list_nodes(
        TenantId("0a000000-0000-4000-a000-000000000001"),
        PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    new_ids = {node.id.value for node in after} - before
    assert memory.event_id.value in new_ids
    created = next(node for node in after if node.id == memory.event_id)
    assert created.is_key() is True
    assert created.type == "milestone"
    edges = events.list_edges(
        TenantId("0a000000-0000-4000-a000-000000000001"),
        PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    assert any(edge.to_id == memory.event_id for edge in edges)
