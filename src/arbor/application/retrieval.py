from __future__ import annotations

from collections import defaultdict

from arbor.application.event_graph_router import expand_event_nodes, route_event_seeds
from arbor.application.query_planner import plan_queries
from arbor.application.retrieval_config import RetrievalConfig
from arbor.application.retrieval_lexical import (
    lexical_token_score,
    mmr_select,
    rrf_merge,
    score_memory,
)
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.memory.memory import MemoryItem, MemoryType
from arbor.domain.shared.ids import PersonaId, TenantId

STRATEGIES = ("summary_only", "vector_only", "layered", "layered_tree")


def _apply_vector_filters(item: MemoryItem, filters: dict | None) -> bool:
    if not filters:
        return True
    event_ids = filters.get("event_ids")
    if event_ids is not None:
        allowed = {str(value) for value in event_ids}
        event_id = item.event_id.value if item.event_id else None
        if event_id is None or event_id not in allowed:
            return False
    types = filters.get("types")
    if types is not None:
        allowed_types = {str(value) for value in types}
        if item.type.value not in allowed_types:
            return False
    exclude_ids = filters.get("exclude_ids")
    return exclude_ids is None or item.id.value not in {str(value) for value in exclude_ids}


def _lexical_scan(memories: list[MemoryItem], query: str, k: int) -> list[MemoryItem]:
    scored = [
        (item, lexical_token_score(query, item.text or ""))
        for item in memories
        if item.is_searchable()
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [item for item, score in scored if score > 0][:k]


def _merge_vector_hits(
    global_hits: list[tuple[MemoryItem, float]],
    scoped_hits: list[tuple[MemoryItem, float]],
) -> list[MemoryItem]:
    global_rank = [item for item, _ in global_hits]
    scoped_rank = [item for item, _ in scoped_hits]
    if scoped_rank:
        return rrf_merge([scoped_rank, global_rank])
    return global_rank


def rerank_memories(
    query: str,
    candidates: list[MemoryItem],
    embed,
    limit: int = 6,
    config: RetrievalConfig | None = None,
) -> tuple[list[MemoryItem], dict[str, float]]:
    cfg = config or RetrievalConfig.from_env()
    if not candidates:
        return [], {}
    query_vector = embed(query)
    scored = [
        (
            item,
            score_memory(
                query,
                item,
                embed,
                fact_weight=cfg.type_weight_fact,
                chunk_weight=cfg.type_weight_chunk,
                query_vector=query_vector,
            ),
        )
        for item in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    positive = [(item, score) for item, score in scored if score > 0]
    selected = mmr_select(positive, embed, limit, lambda_=cfg.mmr_lambda)
    hit_scores = {item.id.value: score for item, score in positive}
    return selected, hit_scores


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
    edges: list[EventEdge] | None = None,
    config: RetrievalConfig | None = None,
    k_pool: int | None = None,
    k_rerank: int | None = None,
    lexical_search=None,
) -> dict:
    """Return hit layers. Isolation is the caller's VectorIndex filter."""
    if strategy not in STRATEGIES:
        raise ValueError(strategy)

    cfg = config or RetrievalConfig.from_env()
    final_k = k_rerank if k_rerank is not None else min(k, cfg.rerank_k)
    pool_k = k_pool if k_pool is not None else max(cfg.pool_k, k, final_k)
    edge_list = edges or []

    profile_hits: list[MemoryItem] = []
    event_hits: list[MemoryItem] = []
    vector_hits: list[MemoryItem] = []
    event_nodes: list[EventNode] = []
    per_source_counts: dict[str, int] = defaultdict(int)
    sub_queries_used: list[dict] = []
    rag_pool: list[MemoryItem] = []
    seen_pool: set[str] = set()
    seen_vector: set[str] = set()
    seen_event_hit: set[str] = set()
    seen_event_node: set[str] = set()

    if strategy in {"layered", "layered_tree"}:
        profile_hits = [
            memory
            for memory in memories
            if memory.is_searchable() and memory.type is MemoryType.FACT and memory.event_id is None
        ]
        per_source_counts["profile"] = len(profile_hits)

    planned = plan_queries(query, cfg.query_plan) if strategy != "summary_only" else []
    if not planned:
        planned = [{"query": query, "intent": "general"}]

    for plan in planned:
        sub_query = plan["query"]
        intent = plan.get("intent") or "general"
        sub_queries_used.append({"query": sub_query, "intent": intent})

        expanded_event_ids: set[str] = set()
        event_hits_batch: list[MemoryItem] = []

        if strategy == "layered_tree":
            seeds = route_event_seeds(sub_query, events, embed, cfg.event_seed_k)
            sub_event_nodes, expanded_event_ids = expand_event_nodes(
                seeds,
                events,
                edge_list,
                depth=cfg.event_expand_depth,
                max_events=cfg.event_expand_max,
            )
            for node in sub_event_nodes:
                if node.id.value not in seen_event_node:
                    event_nodes.append(node)
                    seen_event_node.add(node.id.value)
            event_ids = expanded_event_ids or {node.id.value for node in sub_event_nodes}
            event_hits_batch = [
                memory
                for memory in memories
                if memory.is_searchable() and memory.event_id and memory.event_id.value in event_ids
            ]
            for memory in event_hits_batch:
                if memory.id.value not in seen_event_hit:
                    event_hits.append(memory)
                    seen_event_hit.add(memory.id.value)

        if strategy in {"vector_only", "layered", "layered_tree"} and intent != "profile":
            sub_pool_k = max(10, pool_k // max(1, len(planned)))
            exclude_ids = {memory.id.value for memory in profile_hits + event_hits}
            qv = embed(sub_query)
            global_raw = vector_search(
                tenant_id=tenant_id,
                persona_id=persona_id,
                query_vector=qv,
                k=sub_pool_k,
            )
            scoped_raw: list[tuple[MemoryItem, float]] = []
            if expanded_event_ids:
                scoped_raw = vector_search(
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    query_vector=qv,
                    k=max(10, sub_pool_k // 2),
                    filters={
                        "event_ids": list(expanded_event_ids),
                        "exclude_ids": list(exclude_ids),
                    },
                )

            merged_vectors = _merge_vector_hits(global_raw, scoped_raw)
            merged_vectors = [
                item
                for item in merged_vectors
                if item.id.value not in exclude_ids and _apply_vector_filters(item, None)
            ]

            if cfg.hybrid_enabled:
                exclude = list(exclude_ids)
                lexical_items: list[MemoryItem] = []
                if lexical_search is not None:
                    lexical_items = lexical_search(
                        tenant_id,
                        persona_id,
                        sub_query,
                        sub_pool_k,
                        filters={"exclude_ids": exclude} if exclude else None,
                    )
                else:
                    lexical_items = _lexical_scan(memories, sub_query, sub_pool_k)
                    lexical_items = [
                        item for item in lexical_items if item.id.value not in exclude_ids
                    ]
                if lexical_items:
                    merged_vectors = rrf_merge([merged_vectors, lexical_items])

            for item in merged_vectors:
                if item.id.value not in seen_vector:
                    vector_hits.append(item)
                    seen_vector.add(item.id.value)

            for item in event_hits_batch + merged_vectors:
                if item.id.value not in seen_pool:
                    rag_pool.append(item)
                    seen_pool.add(item.id.value)

    per_source_counts["event_tree"] = len(event_hits)
    per_source_counts["vector"] = len(vector_hits)

    if strategy != "summary_only":
        rag_hits, all_hit_scores = rerank_memories(query, rag_pool, embed, limit=final_k, config=cfg)
    else:
        rag_hits = []
        all_hit_scores = {}

    scored: list[MemoryItem] = []
    for item in list(profile_hits) + rag_hits:
        if item.id.value not in {existing.id.value for existing in scored}:
            scored.append(item)

    sources: dict[str, str] = {}
    for memory in profile_hits:
        sources[memory.id.value] = "profile"
    for memory in event_hits:
        sources.setdefault(memory.id.value, "event_tree")
    for memory in vector_hits:
        sources.setdefault(memory.id.value, "vector")

    trim_priority = sorted(
        rag_hits,
        key=lambda memory: all_hit_scores.get(memory.id.value, 0.0),
    )

    return {
        "strategy": strategy,
        "summary": summary if strategy != "vector_only" else "",
        "profile_hits": profile_hits,
        "event_hits": event_hits,
        "event_nodes": event_nodes,
        "vector_hits": vector_hits,
        "hits": rag_hits,
        "hit_ids": [memory.id.value for memory in scored],
        "hit_scores": all_hit_scores,
        "trim_priority": [memory.id.value for memory in trim_priority],
        "sources": sources,
        "per_source_counts": dict(per_source_counts),
        "sub_queries": sub_queries_used,
    }
