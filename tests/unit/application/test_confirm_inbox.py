import pytest

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
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
