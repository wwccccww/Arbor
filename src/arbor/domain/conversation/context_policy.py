from __future__ import annotations

from dataclasses import dataclass, field

from arbor.domain.memory.memory import MemoryItem
from arbor.domain.persona.authorization import Capability
from arbor.domain.persona.persona import Profile


@dataclass
class ContextSlots:
    profile: dict = field(default_factory=dict)
    thread_summary: str = ""
    event_hits: list[dict] = field(default_factory=list)
    memory_hits: list[MemoryItem] = field(default_factory=list)
    injected_memory_ids: list[str] = field(default_factory=list)

    def slot_order(self) -> list[str]:
        return ["profile", "thread_summary", "event_hits", "memory_hits"]


class ContextPolicy:
    """Define slot priority. Does not perform I/O."""

    max_memories = 5

    def min_profile(self, profile: Profile) -> dict:
        return {"display_name": profile.display_name, "one_liner": profile.one_liner}

    def full_profile(self, profile: Profile) -> dict:
        data = self.min_profile(profile)
        data["taboos"] = list(profile.taboos)
        data["relationships"] = list(profile.relationships)
        return data

    def build_without_memory(self, profile: Profile, summary: str = "") -> ContextSlots:
        return ContextSlots(profile=self.min_profile(profile), thread_summary=summary)

    def assemble(
        self,
        *,
        profile: Profile,
        capabilities: list[Capability],
        summary: str,
        event_hits: list[dict],
        memory_hits: list[MemoryItem],
    ) -> ContextSlots:
        can_read = Capability.READ_MEMORY in capabilities
        if not can_read:
            return self.build_without_memory(profile, summary="")
        hits = [m for m in memory_hits if m.is_searchable()][: self.max_memories]
        slots = ContextSlots(
            profile=self.full_profile(profile),
            thread_summary=summary,
            event_hits=event_hits,
            memory_hits=hits,
            injected_memory_ids=[m.id.value for m in hits],
        )
        return slots
