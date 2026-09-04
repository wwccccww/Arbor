from arbor.domain.conversation.context_policy import ContextPolicy
from arbor.domain.persona.authorization import Capability
from arbor.domain.persona.persona import Profile


def test_context_policy():
    policy = ContextPolicy()
    slots = policy.assemble(
        profile=Profile(display_name="林夏", one_liner="hi", taboos=["香菜"]),
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
        summary="摘要",
        event_hits=[{"title": "e"}],
        memory_hits=[],
    )
    assert slots.slot_order() == [
        "profile",
        "tool_policy",
        "thread_summary",
        "recent_turns",
        "event_hits",
        "memory_hits",
    ]
    assert slots.thread_summary == "摘要"
def test_context_policy_caps_memories_at_five_after_policy_reorder():
    from arbor.domain.memory.memory import MemoryItem, MemoryType
    from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId

    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    hits = [
        MemoryItem(
            id=MemoryId(f"0a000000-0000-4000-a000-00000000030{i}"),
            tenant_id=tenant,
            persona_id=persona,
            text=f"fact {i}",
            type=MemoryType.FACT,
        )
        for i in range(6)
    ]
    slots = ContextPolicy().assemble(
        profile=Profile(display_name="林夏", one_liner="hi"),
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
        summary="",
        event_hits=[],
        memory_hits=hits,
    )
    assert len(slots.memory_hits) == 5
    assert len(slots.injected_memory_ids) == 5
