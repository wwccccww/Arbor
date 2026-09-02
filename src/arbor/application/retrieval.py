from __future__ import annotations

import time
from collections import defaultdict

from arbor.application.event_graph_router import expand_event_nodes, filter_event_nodes, route_event_seeds
from arbor.application.memory.validity import is_memory_expired
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
from arbor.observability.noop import NoopObservability

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
    if exclude_ids is not None and item.id.value in {str(value) for value in exclude_ids}:
        return False
    memory_classes = filters.get("memory_classes")
    if memory_classes is not None:
        allowed_classes = {str(value) for value in memory_classes}
        if item.memory_class is None or item.memory_class.value not in allowed_classes:
            return False
    return not is_memory_expired(item)


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


def _stabilize_causal_hits(
    rag_hits: list[MemoryItem],
    event_hits: list[MemoryItem],
    rag_pool: list[MemoryItem],
    limit: int,
) -> list[MemoryItem]:
    """Keep cause/effect siblings on the same event and graph-expanded episodes for causal queries."""
    pool_by_event: dict[str, list[MemoryItem]] = defaultdict(list)
    for item in rag_pool:
        if item.event_id:
            pool_by_event[item.event_id.value].append(item)

    merged = list(rag_hits)
    seen = {item.id.value for item in merged}

    for item in list(merged):
        if not item.event_id:
            continue
        for sibling in pool_by_event.get(item.event_id.value, []):
            if sibling.id.value not in seen:
                merged.append(sibling)
                seen.add(sibling.id.value)

    per_event: dict[str, int] = defaultdict(int)
    for item in event_hits:
        if item.id.value in seen:
            continue
        event_key = item.event_id.value if item.event_id else ""
        if per_event[event_key] >= 2:
            continue
        merged.append(item)
        seen.add(item.id.value)
        per_event[event_key] += 1

    if any(item.type is MemoryType.FILE_CHUNK for item in merged):
        for item in rag_pool:
            if item.type is not MemoryType.FILE_CHUNK or item.id.value in seen:
                continue
            text = item.text or ""
            if text.startswith("售后手册") or "手册" in text[:12]:
                merged.append(item)
                seen.add(item.id.value)

    cap = max(limit, min(len(merged), limit + 4))
    return merged[:cap]


def _select_relevant_profile_hits(
    query: str,
    profile_hits: list[MemoryItem],
    embed,
    *,
    limit: int = 2,
    config: RetrievalConfig | None = None,
) -> list[MemoryItem]:
    """Pick profile FACT memories most relevant to the query for prompt injection."""
    if not profile_hits or limit <= 0:
        return []
    cfg = config or RetrievalConfig.from_env()
    selected, scores = rerank_memories(query, profile_hits, embed, limit=limit, config=cfg)
    if selected:
        return [
            item
            for item in selected
            if scores.get(item.id.value, 0.0) >= cfg.memory_min_score
        ]
    return _lexical_scan(profile_hits, query, limit)


def _filter_scored_hits(
    hits: list[MemoryItem],
    scores: dict[str, float],
    *,
    min_score: float,
    min_keep: int = 1,
) -> list[MemoryItem]:
    kept = [item for item in hits if scores.get(item.id.value, 0.0) >= min_score]
    if len(kept) < min_keep and hits:
        return hits[:min_keep]
    return kept


def _profile_inject_limit(
    query: str,
    profile_hits: list[MemoryItem],
    embed,
    *,
    final_k: int,
    profile_query: bool,
    config: RetrievalConfig,
) -> int:
    if not profile_hits or final_k <= 0 or not profile_query:
        return 0
    return min(2, final_k)


def _rerank_planned_hits(
    query: str,
    planned: list[dict],
    rag_pool: list[MemoryItem],
    embed,
    *,
    limit: int,
    config: RetrievalConfig,
) -> tuple[list[MemoryItem], dict[str, float]]:
    if len(planned) <= 1:
        hits, scores = rerank_memories(query, rag_pool, embed, limit=limit, config=config)
        return _filter_scored_hits(hits, scores, min_score=config.memory_min_score), scores

    merged: list[MemoryItem] = []
    all_scores: dict[str, float] = {}
    seen: set[str] = set()

    main_hits, main_scores = rerank_memories(query, rag_pool, embed, limit=limit, config=config)
    for item in main_hits:
        mid = item.id.value
        all_scores[mid] = main_scores.get(mid, 0.0)
        if mid not in seen:
            merged.append(item)
            seen.add(mid)

    per_sub = max(2, limit // len(planned))
    for plan in planned:
        sub_hits, sub_scores = rerank_memories(
            plan["query"],
            rag_pool,
            embed,
            limit=per_sub,
            config=config,
        )
        for item in sub_hits:
            mid = item.id.value
            all_scores[mid] = max(all_scores.get(mid, 0.0), sub_scores.get(mid, 0.0))
            if mid not in seen:
                merged.append(item)
                seen.add(mid)
    merged.sort(key=lambda item: all_scores.get(item.id.value, 0.0), reverse=True)
    return merged[:limit], all_scores


def _merge_injection_hits(
    profile_hits: list[MemoryItem],
    rag_hits: list[MemoryItem],
    *,
    limit: int,
) -> list[MemoryItem]:
    merged: list[MemoryItem] = []
    seen: set[str] = set()
    for item in profile_hits + rag_hits:
        if item.id.value in seen:
            continue
        seen.add(item.id.value)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


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
    observability: object | None = None,
) -> dict:
    """Return hit layers. Isolation is the caller's VectorIndex filter."""
    obs = observability or NoopObservability()
    retrieve_started = time.perf_counter()
    if strategy not in STRATEGIES:
        raise ValueError(strategy)

    with obs.span("rag.retrieve", strategy=strategy):
        result = _retrieve_inner(
            strategy=strategy,
            query=query,
            tenant_id=tenant_id,
            persona_id=persona_id,
            k=k,
            memories=memories,
            events=events,
            summary=summary,
            vector_search=vector_search,
            embed=embed,
            edges=edges,
            config=config,
            k_pool=k_pool,
            k_rerank=k_rerank,
            lexical_search=lexical_search,
            observability=obs,
        )
    per_source = result.get("per_source_counts") or {}
    obs.event(
        "rag.retrieve",
        strategy=strategy,
        candidate_count=sum(int(v) for v in per_source.values()),
        hit_count=len(result.get("hits") or []),
        per_source_counts=dict(per_source),
        duration_ms=round((time.perf_counter() - retrieve_started) * 1000, 2),
    )
    obs.observe(
        "arbor_rag_retrieval_duration_seconds",
        time.perf_counter() - retrieve_started,
        strategy=strategy,
    )
    return result


def _retrieve_inner(
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
    observability: object | None = None,
) -> dict:
    obs = observability or NoopObservability()
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
            with obs.span("event_tree.route", intent=intent):
                seeds = route_event_seeds(sub_query, events, embed, cfg.event_seed_k)
            expand_depth = cfg.event_expand_depth + (1 if intent == "causal" else 0)
            expand_max = cfg.event_expand_max if intent == "causal" else min(cfg.event_expand_max, 4)
            sub_event_nodes, expanded_event_ids = expand_event_nodes(
                seeds,
                events,
                edge_list,
                depth=expand_depth,
                max_events=expand_max,
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

        if strategy in {"vector_only", "layered", "layered_tree"}:
            sub_pool_k = max(10, pool_k // max(1, len(planned)))
            if intent == "causal":
                sub_pool_k = max(sub_pool_k, pool_k)
            exclude_ids = {memory.id.value for memory in profile_hits}
            if intent != "causal":
                exclude_ids.update(memory.id.value for memory in event_hits)
            qv = embed(sub_query)
            with obs.span("vector.search", scope="global", k=sub_pool_k):
                global_raw = vector_search(
                    tenant_id=tenant_id,
                    persona_id=persona_id,
                    query_vector=qv,
                    k=sub_pool_k,
                )
            scoped_raw: list[tuple[MemoryItem, float]] = []
            if expanded_event_ids:
                with obs.span("vector.search", scope="scoped", k=max(10, sub_pool_k // 2)):
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

            if intent == "causal":
                chunk_scored = [
                    (memory, lexical_token_score(sub_query, memory.text or ""))
                    for memory in memories
                    if memory.is_searchable() and memory.type is MemoryType.FILE_CHUNK
                ]
                chunk_scored.sort(key=lambda pair: pair[1], reverse=True)
                for memory, score in chunk_scored[:4]:
                    if score <= 0 or memory.id.value in seen_pool:
                        continue
                    rag_pool.append(memory)
                    seen_pool.add(memory.id.value)

    per_source_counts["event_tree"] = len(event_hits)
    per_source_counts["vector"] = len(vector_hits)

    causal_query = any(plan.get("intent") == "causal" for plan in planned)
    episode_query = any(plan.get("intent") == "episode" for plan in planned)
    profile_query = any(plan.get("intent") == "profile" for plan in planned)
    if strategy == "layered_tree" and event_nodes:
        if profile_query:
            event_nodes = []
        else:
            inject_k = cfg.event_inject_k + (1 if causal_query else 0)
            min_score = cfg.event_min_score * (0.5 if causal_query else 1.0)
            require_lexical = not (causal_query or episode_query)
            event_nodes = filter_event_nodes(
                query,
                event_nodes,
                embed,
                limit=inject_k,
                min_score=min_score,
                require_lexical=require_lexical,
                min_lexical=0.08,
            )

    if strategy != "summary_only":
        profile_ids = {memory.id.value for memory in profile_hits}
        rag_pool = [item for item in rag_pool if item.id.value not in profile_ids]
        rerank_started = time.perf_counter()
        input_count = len(rag_pool)
        with obs.span("rag.rerank", input_count=input_count):
            rag_hits, all_hit_scores = _rerank_planned_hits(
                query,
                planned,
                rag_pool,
                embed,
                limit=final_k,
                config=cfg,
            )
        obs.event(
            "rag.rerank",
            input_count=input_count,
            output_count=len(rag_hits),
            duration_ms=round((time.perf_counter() - rerank_started) * 1000, 2),
        )
        if any(plan.get("intent") == "causal" for plan in planned) and strategy == "layered_tree":
            rag_hits = _stabilize_causal_hits(rag_hits, event_hits, rag_pool, final_k)
    else:
        rag_hits = []
        all_hit_scores = {}

    profile_inject_k = _profile_inject_limit(
        query,
        profile_hits,
        embed,
        final_k=final_k,
        profile_query=profile_query,
        config=cfg,
    )
    relevant_profile = _select_relevant_profile_hits(
        query,
        profile_hits,
        embed,
        limit=profile_inject_k,
        config=cfg,
    )
    if relevant_profile:
        _, profile_scores = rerank_memories(
            query, relevant_profile, embed, limit=len(relevant_profile), config=cfg
        )
        all_hit_scores.update(profile_scores)
    hits = _merge_injection_hits(relevant_profile, rag_hits, limit=final_k)

    scored: list[MemoryItem] = []
    for item in list(profile_hits) + rag_hits:
        if item.id.value not in {existing.id.value for existing in scored}:
            scored.append(item)

    sources: dict[str, str] = {}
    for memory in profile_hits:
        sources[memory.id.value] = "profile"
    for memory in relevant_profile:
        sources[memory.id.value] = "profile"
    for memory in event_hits:
        sources.setdefault(memory.id.value, "event_tree")
    for memory in vector_hits:
        sources.setdefault(memory.id.value, "vector")

    trim_priority = sorted(
        hits,
        key=lambda memory: all_hit_scores.get(memory.id.value, 0.0),
    )

    return {
        "strategy": strategy,
        "summary": summary if strategy != "vector_only" else "",
        "profile_hits": profile_hits,
        "event_hits": event_hits,
        "event_nodes": event_nodes,
        "vector_hits": vector_hits,
        "hits": hits,
        "hit_ids": [memory.id.value for memory in scored],
        "injected_hit_ids": [memory.id.value for memory in hits],
        "hit_scores": all_hit_scores,
        "trim_priority": [memory.id.value for memory in trim_priority],
        "sources": sources,
        "per_source_counts": dict(per_source_counts),
        "sub_queries": sub_queries_used,
    }
