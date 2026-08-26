from __future__ import annotations

from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    SeqIdGenerator,
)
from arbor.application.memory.bootstrap_from_inbox import BootstrapFromInbox
from arbor.application.memory.commands import ConfirmInboxItem
from arbor.domain.memory.memory import InboxItem
from arbor.domain.persona.authorization import (
    AuthorizationPolicy,
    Capability,
    Grant,
    Persona,
    Profile,
)
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def _setup():
    stores = InMemoryStores()
    tenant_id = TenantId("tenant-a")
    user_id = UserId("user-a")
    persona = Persona(
        id=PersonaId("persona-a"),
        tenant_id=tenant_id,
        skin="companion",
        profile=Profile(display_name="林夏", one_liner=""),
        grants=[Grant(user_id=user_id, capabilities=list(Capability))],
    )
    personas = InMemoryPersonaRepository(stores)
    personas.save(persona)
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    inbox.add(
        InboxItem(
            id="inbox-event",
            tenant_id=tenant_id,
            persona_id=persona.id,
            kind="event",
            payload={"text": "去年十一月在面店吵架", "memory_type": "fact"},
        )
    )
    inbox.add(
        InboxItem(
            id="inbox-fact",
            tenant_id=tenant_id,
            persona_id=persona.id,
            kind="fact",
            payload={"text": "讨厌香菜", "memory_type": "fact"},
        )
    )
    vectors = InMemoryVectorIndex(stores, memories)
    ids = SeqIdGenerator()

    class FakeEmbed:
        def embed(self, text: str) -> list[float]:
            return [0.1, 0.2]

    auth = AuthorizationPolicy()
    from arbor.adapters.outbound.inmemory import InMemoryEventGraphRepository

    events_repo = InMemoryEventGraphRepository(stores)
    confirm = ConfirmInboxItem(
        personas=personas,
        memories=memories,
        inbox=inbox,
        vectors=vectors,
        embed=FakeEmbed(),
        ids=ids,
        auth=auth,
        events=events_repo,
    )
    bootstrap = BootstrapFromInbox(
        personas=personas,
        inbox=inbox,
        confirm=confirm,
        auth=auth,
    )
    return tenant_id, user_id, persona.id, bootstrap, personas, events_repo, memories


def test_bootstrap_updates_profile_and_events():
    tenant_id, user_id, persona_id, bootstrap, personas, events_repo, memories = _setup()
    result = bootstrap(
        tenant_id=tenant_id,
        user_id=user_id,
        persona_id=persona_id,
    )
    persona = personas.get(tenant_id, persona_id)
    assert result["events_created"] == 1
    assert result["memories_created"] == 2
    assert persona.profile.one_liner
    assert "香菜" in persona.profile.taboos[0]
    assert len(events_repo.list_nodes(tenant_id, persona_id)) == 1
    assert len(memories.list_active(tenant_id, persona_id)) == 2
