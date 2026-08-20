from __future__ import annotations

from pathlib import Path

import yaml

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryEventGraphRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryObjectStorage,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryThreadRepository,
    InMemoryVectorIndex,
    ScriptedLLM,
    ScriptedReasoner,
    SeqIdGenerator,
    fixture_embed,
)
from arbor.application.conversation.send_message import SendMessage
from arbor.application.memory.commands import ConfirmInboxItem, ImportArtifact
from arbor.domain.conversation.thread import Thread
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventNode
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId

ROOT = Path(__file__).resolve().parents[3]
USER = UserId("0a000000-0000-4000-a000-000000000002")


def load_mini(stores: InMemoryStores) -> None:
    data = yaml.safe_load((ROOT / "tests/fixtures/mini-world.yaml").read_text(encoding="utf-8"))
    for p in data["personas"]:
        stores.personas[p["id"]] = Persona(
            id=PersonaId(p["id"]),
            tenant_id=TenantId(p["tenant_id"]),
            skin="companion",
            profile=Profile(
                display_name=p["display_name"],
                one_liner=p.get("one_liner", ""),
                taboos=list(p.get("taboos") or []),
            ),
            grants=[Grant(user_id=USER, capabilities=list(Capability))],
        )
    for t in data.get("threads", []):
        stores.threads[t["id"]] = Thread(
            id=ThreadId(t["id"]),
            tenant_id=TenantId(t["tenant_id"]),
            persona_id=PersonaId(t["persona_id"]),
            summary=t.get("summary", ""),
        )
    for e in data.get("event_nodes", []):
        stores.events[e["id"]] = EventNode(
            id=EventId(e["id"]),
            tenant_id=TenantId(e["tenant_id"]),
            persona_id=PersonaId(e["persona_id"]),
            title=e.get("title", ""),
        )
    mem_repo = InMemoryMemoryRepository(stores)
    index = InMemoryVectorIndex(stores, mem_repo)
    for m in data["memories"]:
        item = MemoryItem(
            id=MemoryId(m["id"]),
            tenant_id=TenantId(m["tenant_id"]),
            persona_id=PersonaId(m["persona_id"]),
            text=m["text"],
            type=MemoryType.FACT,
            status=MemoryStatus(m.get("status", "active")),
            event_id=EventId(m["event_id"]) if m.get("event_id") else None,
        )
        stores.memories[m["id"]] = item
        if item.is_searchable():
            index.upsert(item.tenant_id, item.persona_id, item.id, fixture_embed(item.text), item.status)


def _stack(extra_citation=None, proposed_fact=None):
    stores = InMemoryStores()
    load_mini(stores)
    memories = InMemoryMemoryRepository(stores)
    return stores, SendMessage(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        threads=InMemoryThreadRepository(stores),
        events=InMemoryEventGraphRepository(stores),
        inbox=InMemoryInboxRepository(stores),
        vectors=InMemoryVectorIndex(stores, memories),
        llm=ScriptedLLM(extra_citation_memory_id=extra_citation),
        reasoner=ScriptedReasoner(proposed_fact=proposed_fact),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )


def test_send_message_context_order():
    stores, send = _stack()
    out = send(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        thread_id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text="我们上次为什么吵架？",
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
    )
    assert out["slot_order"] == ["profile", "thread_summary", "event_hits", "memory_hits"]


def test_send_message_no_memory_without_grant():
    stores, send = _stack()
    out = send(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        thread_id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text="随便聊聊",
        capabilities=[Capability.CHAT],
    )
    blob = str(out["prompt_slots"])
    assert "香菜" not in blob
    assert "老张面馆" not in blob
    assert out["injected_memory_ids"] == []


def test_send_message_drop_hallucinated_citation():
    stores, send = _stack(extra_citation="0a000000-0000-4000-a000-000000000401")
    out = send(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        thread_id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text="我们在哪吵的？",
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
    )
    assert "0a000000-0000-4000-a000-000000000401" not in out["citations"]


def test_send_message_extract_goes_to_inbox():
    stores, send = _stack(proposed_fact="林夏最近开始喝美式")
    before = len(stores.memories)
    out = send(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        thread_id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text="我最近喜欢喝美式",
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
    )
    assert out["inbox_added"] == 1
    assert len(stores.memories) == before


def test_confirm_inbox_makes_searchable():
    stores, send = _stack()
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    vectors = InMemoryVectorIndex(stores, memories)
    inbox.add(
        InboxItem(
            id="pending-1",
            tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
            persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            kind="fact",
            payload={"text": "林夏最近开始喝美式"},
        )
    )
    confirm = ConfirmInboxItem(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        inbox=inbox,
        vectors=vectors,
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    item = confirm(
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        user_id=USER,
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        capabilities=list(Capability),
    )
    hits = vectors.search(
        tenant_id=item.tenant_id,
        persona_id=item.persona_id,
        query_vector=fixture_embed("林夏最近开始喝美式"),
        k=5,
    )
    assert any(h[0].id == item.id for h in hits)


def test_import_requires_write_memory():
    stores, _send = _stack()
    storage = InMemoryObjectStorage(stores)
    cmd = ImportArtifact(personas=InMemoryPersonaRepository(stores), storage=storage, auth=AuthorizationPolicy())
    try:
        cmd(
            tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
            user_id=USER,
            persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
            filename="notes.pdf",
            capabilities=[Capability.CHAT, Capability.READ_MEMORY],
        )
        raise AssertionError("should fail")
    except DomainError as exc:
        assert exc.code == "FORBIDDEN_MEMORY_WRITE"
    assert storage.count() == 0


def test_vector_fake_index_isolates_persona():
    stores, _send = _stack()
    memories = InMemoryMemoryRepository(stores)
    index = InMemoryVectorIndex(stores, memories)
    vec = [0.1, 0.2, 0.3] + [0.0] * 61
    a = MemoryItem(
        id=MemoryId("mem-a"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        text="同一句秘密",
    )
    b = MemoryItem(
        id=MemoryId("mem-b"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000020"),
        text="同一句秘密",
    )
    memories.save(a)
    memories.save(b)
    index.upsert(a.tenant_id, a.persona_id, a.id, vec, a.status)
    index.upsert(b.tenant_id, b.persona_id, b.id, vec, b.status)
    hits = index.search(tenant_id=b.tenant_id, persona_id=b.persona_id, query_vector=vec, k=5)
    assert all(h[0].persona_id == b.persona_id for h in hits)
    assert all(h[0].id != a.id for h in hits)
    assert any(h[0].id == b.id for h in hits)
