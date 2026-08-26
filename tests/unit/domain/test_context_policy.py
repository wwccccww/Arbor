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
    assert "taboos" in slots.profile
