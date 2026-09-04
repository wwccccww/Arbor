from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.memory.memory import MemoryItem
from arbor.domain.persona.authorization import Capability, ToolPolicy
from arbor.domain.persona.persona import Profile


@dataclass
class ContextSlots:
    profile: dict = field(default_factory=dict)
    thread_summary: str = ""
    recent_turns: list[dict] = field(default_factory=list)
    event_hits: list[dict] = field(default_factory=list)
    memory_hits: list[MemoryItem] = field(default_factory=list)
    injected_memory_ids: list[str] = field(default_factory=list)
    tool_policy: dict = field(default_factory=dict)

    def slot_order(self) -> list[str]:
        return [
            "profile",
            "tool_policy",
            "thread_summary",
            "recent_turns",
            "event_hits",
            "memory_hits",
        ]


class ContextPolicy:
    """Define slot priority. Does not perform I/O."""

    max_memories = 8

    def min_profile(self, profile: Profile) -> dict:
        data = {"display_name": profile.display_name, "one_liner": profile.one_liner}
        if profile.avatar:
            data["avatar"] = profile.avatar
        return data

    def full_profile(self, profile: Profile) -> dict:
        data = self.min_profile(profile)
        data["taboos"] = list(profile.taboos)
        data["relationships"] = list(profile.relationships)
        return data

    def build_without_memory(self, profile: Profile, summary: str = "") -> ContextSlots:
        return ContextSlots(profile=self.min_profile(profile), thread_summary=summary)

    def tool_policy_slot(self, tool_policy: ToolPolicy | None) -> dict:
        if tool_policy is None:
            return {}
        allowed = [str(item) for item in tool_policy.allowed_tools if str(item).strip()]
        notes = (tool_policy.notes or "").strip()
        if not allowed and not notes:
            return {}
        return {
            "allowed_tools": allowed,
            "notes": notes,
        }

    def assemble(
        self,
        *,
        profile: Profile,
        capabilities: list[Capability],
        summary: str,
        event_hits: list[dict],
        memory_hits: list[MemoryItem],
        tool_policy: ToolPolicy | None = None,
    ) -> ContextSlots:
        can_read = Capability.READ_MEMORY in capabilities
        policy_slot = self.tool_policy_slot(tool_policy)
        if not can_read:
            slots = self.build_without_memory(profile, summary="")
            slots.tool_policy = policy_slot
            return slots
        hits = [m for m in memory_hits if m.is_searchable()][: self.max_memories]
        slots = ContextSlots(
            profile=self.full_profile(profile),
            thread_summary=summary,
            event_hits=event_hits,
            memory_hits=hits,
            injected_memory_ids=[m.id.value for m in hits],
            tool_policy=policy_slot,
        )
        return slots
