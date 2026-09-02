from __future__ import annotations

from dataclasses import dataclass

from arbor.env import (
    retrieval_event_expand_depth,
    retrieval_event_expand_max,
    retrieval_event_inject_k,
    retrieval_event_min_score,
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
    event_inject_k: int = 2
    event_min_score: float = 0.08
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
            event_inject_k=retrieval_event_inject_k(),
            event_min_score=retrieval_event_min_score(),
            hybrid_enabled=retrieval_hybrid_enabled(),
            query_plan=retrieval_query_plan(),
            mmr_lambda=retrieval_mmr_lambda(),
            type_weight_fact=retrieval_type_weight_fact(),
            type_weight_chunk=retrieval_type_weight_chunk(),
        )

    @classmethod
    def ragas_tuned(cls) -> RetrievalConfig:
        """RAGAS official preset: same prompt_k as default, tighter pool/rerank + higher MMR."""
        return cls(
            pool_k=20,
            rerank_k=4,
            prompt_k=5,
            event_seed_k=2,
            event_expand_depth=2,
            event_expand_max=8,
            hybrid_enabled=True,
            query_plan="rules",
            mmr_lambda=0.85,
            type_weight_fact=1.0,
            type_weight_chunk=0.6,
        )

