from __future__ import annotations

from arbor.application.retrieval_lexical import lexical_token_score
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.shared.textvec import cosine, fixture_embed

EXPAND_EDGE_KINDS = frozenset({"temporal", "caused_by"})


def _score_event(query: str, event: EventNode, embed) -> float:
    blob = f"{event.title} {event.summary}"
    return lexical_token_score(query, blob) + cosine(embed(query), embed(blob))


def route_event_seeds(
    query: str,
    events: list[EventNode],
    embed,
    seed_k: int,
    min_score: float = 0.05,
) -> list[EventNode]:
    scored = [(event, _score_event(query, event, embed)) for event in events]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [event for event, score in scored if score > min_score][:seed_k]


def expand_event_nodes(
    seeds: list[EventNode],
    all_events: list[EventNode],
    edges: list[EventEdge],
    *,
    depth: int,
    max_events: int,
) -> tuple[list[EventNode], set[str]]:
    id_to_node = {event.id.value: event for event in all_events}
    expanded_ids: set[str] = {event.id.value for event in seeds}
    frontier = set(expanded_ids)
    for _ in range(max(0, depth)):
        if len(expanded_ids) >= max_events:
            break
        next_ids: set[str] = set()
        for edge in edges:
            if edge.kind not in EXPAND_EDGE_KINDS:
                continue
            if edge.from_id.value in frontier and edge.to_id.value not in expanded_ids:
                next_ids.add(edge.to_id.value)
            if edge.to_id.value in frontier and edge.from_id.value not in expanded_ids:
                next_ids.add(edge.from_id.value)
        if not next_ids:
            break
        for event_id in next_ids:
            if len(expanded_ids) >= max_events:
                break
            expanded_ids.add(event_id)
        frontier = next_ids
    nodes = [id_to_node[event_id] for event_id in expanded_ids if event_id in id_to_node]
    return nodes, expanded_ids


def route_events(query: str, events: list[EventNode], limit: int = 2) -> list[EventNode]:
    """Legacy helper for tests; uses fixture embed."""
    scored = []
    for event in events:
        blob = f"{event.title} {event.summary}"
        scored.append(
            (
                event,
                lexical_token_score(query, blob)
                + cosine(fixture_embed(query), fixture_embed(blob)),
            )
        )
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [event for event, score in scored if score > 0.05][:limit]

