from __future__ import annotations

from arbor.observability.decision_trace import build_decision_trace_summary


def test_build_decision_trace_summary_hashes_sub_queries():
    summary = build_decision_trace_summary(
        retrieval_meta={
            "strategy": "layered_tree",
            "hit_ids": ["m1", "m2"],
            "sub_queries": [{"query": "去年十一月", "intent": "episode"}],
            "per_source_counts": {"vector": 2},
        },
        token_budget=12000,
        token_estimate=4200,
        injected_memory_ids=["m1"],
        truncation_notes=["trim_vector_low_score:1"],
        reasoner_meta={"called": True, "operation": "extract", "result_kind": "fact"},
        generation_meta={"model": "scripted", "latency_ms": 12, "citation_ids": ["m1"]},
    )
    assert summary["retrieval"]["strategy"] == "layered_tree"
    assert summary["context"]["injected_memory_ids"] == ["m1"]
    assert summary["retrieval"]["sub_queries"][0]["query_hash"].startswith("sha256:")
    assert "去年十一月" not in str(summary)
