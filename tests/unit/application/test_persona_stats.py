from arbor.adapters.outbound.inmemory import (
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryThreadRepository,
)
from arbor.application.persona.persona_stats import build_persona_stats, stats_json
from arbor.domain.conversation.thread import Message, Thread
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability, Grant
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")


def test_build_persona_stats_counts_and_last_message():
    stores, _ = _stack()
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    threads = InMemoryThreadRepository(stores)
    persona = personas.get(TENANT, LINXIA)
    assert persona is not None

    thread = Thread(
        id=ThreadId("0a000000-0000-4000-a000-000000000099"),
        tenant_id=TENANT,
        persona_id=LINXIA,
        messages=[
            Message(role="user", content="还在吗", created_at="2026-08-27T10:00:00+00:00"),
            Message(role="assistant", content="在的", created_at="2026-08-27T10:00:01+00:00"),
        ],
    )
    threads.save(thread)

    stats = build_persona_stats(
        persona,
        USER,
        auth=AuthorizationPolicy(),
        memories=memories,
        threads=threads,
    )
    body = stats_json(stats)
    assert body["memory_count"] >= 1
    assert body["thread_count"] >= 1
    assert body["last_interaction"] == "在的"
    assert body["last_interaction_at"] == "2026-08-27T10:00:01+00:00"


def test_build_persona_stats_chat_only_skips_memory_count():
    stores, _ = _stack()
    personas = InMemoryPersonaRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    threads = InMemoryThreadRepository(stores)
    persona = personas.get(TENANT, PersonaId("0a000000-0000-4000-a000-000000000020"))
    assert persona is not None
    persona.grants = [Grant(user_id=USER, capabilities=[Capability.CHAT])]
    stats = build_persona_stats(
        persona,
        USER,
        auth=AuthorizationPolicy(),
        memories=memories,
        threads=threads,
    )
    body = stats_json(stats)
    assert "memory_count" not in body
    assert body.get("thread_count") == 0
