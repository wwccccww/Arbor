from arbor.domain.conversation.context_policy import ContextPolicy
from arbor.domain.persona.authorization import Capability, Profile, ToolPolicy


def test_context_policy_injects_tool_policy():
    policy = ContextPolicy()
    slots = policy.assemble(
        profile=Profile(display_name="林夏", one_liner="陪伴"),
        capabilities=[Capability.READ_MEMORY],
        summary="",
        event_hits=[],
        memory_hits=[],
        tool_policy=ToolPolicy(allowed_tools=["calendar"], notes="仅读日程"),
    )
    assert slots.tool_policy["allowed_tools"] == ["calendar"]
    assert slots.tool_policy["notes"] == "仅读日程"
    assert "tool_policy" in slots.slot_order()
