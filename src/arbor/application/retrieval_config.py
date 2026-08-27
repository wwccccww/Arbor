from __future__ import annotations

from dataclasses import dataclass

from arbor.env import (
    retrieval_event_expand_depth,
    retrieval_event_expand_max,
    retrieval_event_seed_k,
    retrieval_hybrid_enabled,
    retrieval_mmr_lambda,
    retrieval_pool_k,
    retrieval_prompt_k,
    retrieval_query_plan,
    retrieval_rerank_k,
    retrieval_type_weight_chunk,
    retrieval_type_weight_fact,
)


@dataclass(frozen=True)
class RetrievalConfig:
    pool_k: int = 24
    rerank_k: int = 6
    prompt_k: int = 5
    event_seed_k: int = 2
    event_expand_depth: int = 2
    event_expand_max: int = 8
    hybrid_enabled: bool = True
    query_plan: str = "rules"
    mmr_lambda: float = 0.7
    type_weight_fact: float = 1.0
    type_weight_chunk: float = 0.6

    @classmethod
    def from_env(cls) -> RetrievalConfig:
        return cls(
            pool_k=retrieval_pool_k(),
            rerank_k=retrieval_rerank_k(),
            prompt_k=retrieval_prompt_k(),
            event_seed_k=retrieval_event_seed_k(),
            event_expand_depth=retrieval_event_expand_depth(),
            event_expand_max=retrieval_event_expand_max(),
            hybrid_enabled=retrieval_hybrid_enabled(),
            query_plan=retrieval_query_plan(),
            mmr_lambda=retrieval_mmr_lambda(),
            type_weight_fact=retrieval_type_weight_fact(),
            type_weight_chunk=retrieval_type_weight_chunk(),
        )

