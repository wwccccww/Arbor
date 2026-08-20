from __future__ import annotations

from arbor.domain.eventgraph.graph import EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryType
from arbor.domain.shared.ids import PersonaId, TenantId
from arbor.domain.shared.textvec import cosine, fixture_embed


STRATEGIES = ("summary_only", "vector_only", "layered", "layered_tree")


def _lexical(query: str, text: str) -> float:
    if not query or not text:
        return 0.0
    q = set(query)
    t = set(text)
    if not q:
        return 0.0
    return len(q & t) / len(q)


def route_events(query: str, events: list[EventNode], limit: int = 2) -> list[EventNode]:
    scored = []
    for event in events:
        blob = f"{event.title} {event.summary}"
        scored.append((event, _lexical(query, blob) + cosine(fixture_embed(query), fixture_embed(blob))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [e for e, s in scored if s > 0.05][:limit]


def retrieve(
    *,
    strategy: str,
    query: str,
    tenant_id: TenantId,
    persona_id: PersonaId,
    k: int,
    memories: list[MemoryItem],
    events: list[EventNode],
    summary: str,
    vector_search,
    embed,
) -> dict:
    """Return hit layers. Isolation is the caller's VectorIndex filter."""
    if strategy not in STRATEGIES:
        raise ValueError(strategy)

    profile_hits: list[MemoryItem] = []
    event_hits: list[MemoryItem] = []
    vector_hits: list[MemoryItem] = []
    event_nodes: list[EventNode] = []

    if strategy in {"layered", "layered_tree"}:
        profile_hits = [
            m
            for m in memories
            if m.is_searchable() and m.type is MemoryType.FACT and m.event_id is None
        ]

    if strategy == "layered_tree":
        event_nodes = route_events(query, events)
        event_ids = {e.id.value for e in event_nodes}
        event_hits = [m for m in memories if m.is_searchable() and m.event_id and m.event_id.value in event_ids]

    if strategy in {"vector_only", "layered", "layered_tree"}:
        qv = embed(query)
        raw = vector_search(tenant_id=tenant_id, persona_id=persona_id, query_vector=qv, k=k)
        seen = {m.id.value for m in profile_hits + event_hits}
        for item, _score in raw:
            if item.id.value not in seen:
                vector_hits.append(item)

    rag_hits: list[MemoryItem] = []
    if strategy != "summary_only":
        for group in (event_hits, vector_hits):
            for item in group:
                if item.id.value not in {c.id.value for c in rag_hits}:
                    rag_hits.append(item)
        rag_hits = rag_hits[:k]

    scored: list[MemoryItem] = []
    for item in list(profile_hits) + rag_hits:
        if item.id.value not in {c.id.value for c in scored}:
            scored.append(item)

    sources = {}
    for m in profile_hits:
        sources[m.id.value] = "profile"
    for m in event_hits:
        sources.setdefault(m.id.value, "event_tree")
    for m in vector_hits:
        sources.setdefault(m.id.value, "vector")

    return {
        "strategy": strategy,
        "summary": summary if strategy != "vector_only" else "",
        "profile_hits": profile_hits,
        "event_hits": event_hits,
        "event_nodes": event_nodes,
        "vector_hits": vector_hits,
        "hits": rag_hits,
        "hit_ids": [m.id.value for m in scored],
        "sources": sources,
    }
