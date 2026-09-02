from __future__ import annotations

from arbor.application.event_graph_router import expand_event_nodes, filter_event_nodes, route_event_seeds
from arbor.application.query_planner import plan_queries
from arbor.application.retrieval_lexical import lexical_token_score, tokenize
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.shared.ids import EventId, PersonaId, TenantId
from arbor.domain.shared.textvec import fixture_embed

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
PERSONA = PersonaId("0a000000-0000-4000-a000-000000000010")


def _event(event_id: str, title: str, summary: str = "") -> EventNode:
    return EventNode(
        id=EventId(event_id),
        tenant_id=TENANT,
        persona_id=PERSONA,
        title=title,
        summary=summary,
    )


def test_lexical_token_score_handles_shared_terms():
    assert lexical_token_score("讨厌香菜", "林夏讨厌香菜，点餐不能放香菜。") > 0.5


def test_plan_queries_splits_nested_question():
    planned = plan_queries("因为面店吵架，后来怎么样了？", "rules")
    assert len(planned) >= 2


def test_expand_event_nodes_follows_temporal_edge():
    a = _event("0a000000-0000-4000-a000-000000000101", "面店")
    b = _event("0a000000-0000-4000-a000-000000000102", "打电话")
    edges = [
        EventEdge(
            from_id=a.id,
            to_id=b.id,
            kind="temporal",
            tenant_id=TENANT,
            persona_id=PERSONA,
        )
    ]
    expanded, ids = expand_event_nodes([a], [a, b], edges, depth=1, max_events=8)
    assert b.id.value in ids
    assert len(expanded) >= 2


def test_route_event_seeds_returns_matches():
    events = [
        _event("0a000000-0000-4000-a000-000000000101", "面店吵架", "去年11月"),
        _event("0a000000-0000-4000-a000-000000000102", "无关事件", "其他"),
    ]
    seeds = route_event_seeds("面店吵架", events, fixture_embed, seed_k=2)
    assert seeds[0].id.value == "0a000000-0000-4000-a000-000000000101"


def test_filter_event_nodes_drops_irrelevant_events():
    events = [
        _event("0a000000-0000-4000-a000-000000000101", "面店吵架", "因香菜在老张面馆吵架"),
        _event("0a000000-0000-4000-a000-000000000102", "约定每周末打电话", "每周日21:00打电话"),
        _event("0a000000-0000-4000-a000-000000000103", "第一次见面", "在西湖边认识"),
    ]
    filtered = filter_event_nodes(
        "Where does Lin Xia reside in Hangzhou?",
        events,
        fixture_embed,
        limit=2,
        min_score=0.08,
        require_lexical=True,
    )
    assert filtered == []


def test_tokenize_cjk_pairs():
    tokens = tokenize("讨厌香菜")
    assert tokens
