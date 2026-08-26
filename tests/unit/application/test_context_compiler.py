from __future__ import annotations

from arbor.application.conversation.context_budget import truncate_text
from arbor.application.conversation.context_compiler import ContextCompiler
from arbor.domain.conversation.thread import Message, Thread
from arbor.domain.persona.authorization import Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import _stack


def test_context_compiler_includes_recent_turns_and_summary():
    stores, send = _stack()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona_id = PersonaId("0a000000-0000-4000-a000-000000000010")
    thread_id = ThreadId("0a000000-0000-4000-a000-000000000030")
    thread = stores.threads[thread_id.value]
    thread.summary = "更早的摘要"
    thread.messages = [
        Message(role="user", content="第一句"),
        Message(role="assistant", content="第二句"),
    ]
    persona = stores.personas[persona_id.value]
    memories = send.memories.list_active(tenant, persona_id)
    compiler = ContextCompiler(strategy="layered_tree", recent_k=4)
    compiled = compiler.compile(
        persona=persona,
        thread=thread,
        query="第三句",
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
        tenant_id=tenant,
        persona_id=persona_id,
        memories=memories,
        event_nodes=list(stores.events.values()),
        vector_search=send.vectors.search,
        embed=send.embed.embed,
        user_text="第三句",
    )
    assert compiled.prompt_slots["thread_summary"] == "更早的摘要"
    assert len(compiled.prompt_slots["recent_turns"]) == 2
    assert compiled.prompt_slots["recent_turns"][0]["content"] == "第一句"
    assert any("近期对话" in line for line in compiled.injected_contexts)


def test_context_compiler_trims_when_budget_tight():
    stores, send = _stack()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona_id = PersonaId("0a000000-0000-4000-a000-000000000010")
    thread = Thread(
        id=ThreadId("0a000000-0000-4000-a000-000000099"),
        tenant_id=tenant,
        persona_id=persona_id,
        summary="x" * 500,
        messages=[Message(role="user", content="y" * 400)],
    )
    persona = stores.personas[persona_id.value]
    memories = send.memories.list_active(tenant, persona_id)
    compiler = ContextCompiler(
        strategy="layered_tree",
        context_window=800,
        reserved_output=200,
        system_overhead=200,
        recent_k=6,
    )
    compiled = compiler.compile(
        persona=persona,
        thread=thread,
        query="问一句",
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
        tenant_id=tenant,
        persona_id=persona_id,
        memories=memories,
        event_nodes=list(stores.events.values()),
        vector_search=send.vectors.search,
        embed=send.embed.embed,
        user_text="问一句",
    )
    assert compiled.truncation_notes
    assert any(
        note.startswith(("trim_", "truncate_", "drop_")) for note in compiled.truncation_notes
    )


def test_truncate_text_helper():
    assert truncate_text("hello world", 5) == "hell…"
