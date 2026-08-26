from __future__ import annotations

from arbor.domain.eventgraph.graph import EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryType
from arbor.domain.shared.ids import PersonaId, TenantId


def build_persona_eval_cases(
    *,
    tenant_id: TenantId,
    persona_id: PersonaId,
    user_id: str,
    memories: list[MemoryItem],
    events: list[EventNode],
    limit: int = 8,
) -> list[dict]:
    """Lightweight smoke questions from profile facts and key events (not frozen gold)."""
    actor = {
        "tenant_id": tenant_id.value,
        "persona_id": persona_id.value,
        "user_id": user_id,
    }
    other_memory_ids = [
        item.id.value
        for item in memories
        if item.persona_id != persona_id and item.is_searchable()
    ]
    cases: list[dict] = []

    facts = [
        item
        for item in memories
        if item.persona_id == persona_id
        and item.is_searchable()
        and item.type is MemoryType.FACT
        and not item.event_id
    ]
    for item in facts[:3]:
        snippet = (item.text or "").strip()
        if len(snippet) < 6:
            continue
        query = f"关于档案：{snippet[:24]}…" if len(snippet) > 24 else f"档案里有没有提到：{snippet}"
        cases.append(
            {
                "id": f"auto-fact-{item.id.value[-8:]}",
                "actor": actor,
                "query": query,
                "skill": "profile_fact",
                "expected_source": "profile",
                "expected_memory_ids": [item.id.value],
                "forbidden_memory_ids": other_memory_ids,
                "expected_behavior": snippet[:80],
            }
        )

    key_events = [event for event in events if event.persona_id == persona_id and event.is_key()]
    key_events.sort(key=lambda e: e.happened_at or "")
    for event in key_events[:3]:
        title = (event.title or "").strip()
        if not title:
            continue
        related = [
            item.id.value
            for item in memories
            if item.persona_id == persona_id
            and item.is_searchable()
            and item.event_id
            and item.event_id == event.id
        ]
        cases.append(
            {
                "id": f"auto-event-{event.id.value[-8:]}",
                "actor": actor,
                "query": f"还记得「{title}」这件事吗？",
                "skill": "episode_detail",
                "expected_source": "event_tree",
                "expected_event_id": event.id.value,
                "expected_memory_ids": related[:3],
                "forbidden_memory_ids": other_memory_ids,
                "expected_behavior": (event.summary or title)[:80],
            }
        )

    return cases[:limit]
