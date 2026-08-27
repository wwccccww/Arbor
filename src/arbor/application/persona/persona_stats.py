from __future__ import annotations

from dataclasses import dataclass

from arbor.domain.memory.memory import MemoryStatus
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.persona.persona import Persona
from arbor.domain.shared.ids import UserId


@dataclass(frozen=True)
class PersonaStats:
    memory_count: int | None = None
    thread_count: int | None = None
    last_interaction: str | None = None
    last_interaction_at: str | None = None


def _preview(text: str, limit: int = 48) -> str:
    blob = (text or "").strip()
    if not blob:
        return ""
    if len(blob) <= limit:
        return blob
    return f"{blob[: limit - 1]}…"


def build_persona_stats(
    persona: Persona,
    user_id: UserId,
    *,
    auth: AuthorizationPolicy,
    memories,
    threads,
) -> PersonaStats:
    caps = auth.capabilities_for(persona, user_id)
    tenant_id = persona.tenant_id
    persona_id = persona.id

    memory_count: int | None = None
    if Capability.READ_MEMORY in caps:
        memory_count = len(
            memories.list(tenant_id, persona_id, status=MemoryStatus.ACTIVE)
        )

    thread_count: int | None = None
    last_interaction: str | None = None
    last_interaction_at: str | None = None
    if Capability.CHAT in caps:
        thread_list = threads.list(tenant_id, persona_id)
        thread_count = len(thread_list)
        latest_message = None
        latest_at: str | None = None
        for thread in thread_list:
            for message in thread.messages:
                at = getattr(message, "created_at", None)
                if at and (latest_at is None or at > latest_at):
                    latest_at = at
                    latest_message = message
        if latest_message is None:
            for thread in thread_list:
                for message in thread.messages:
                    if (message.content or "").strip():
                        latest_message = message
                        break
                if latest_message is not None:
                    break
        if latest_message is not None:
            last_interaction = _preview(latest_message.content)
            last_interaction_at = getattr(latest_message, "created_at", None) or latest_at

    return PersonaStats(
        memory_count=memory_count,
        thread_count=thread_count,
        last_interaction=last_interaction or None,
        last_interaction_at=last_interaction_at,
    )


def stats_json(stats: PersonaStats) -> dict:
    body: dict = {}
    if stats.memory_count is not None:
        body["memory_count"] = stats.memory_count
    if stats.thread_count is not None:
        body["thread_count"] = stats.thread_count
    if stats.last_interaction:
        body["last_interaction"] = stats.last_interaction
    if stats.last_interaction_at:
        body["last_interaction_at"] = stats.last_interaction_at
    return body
