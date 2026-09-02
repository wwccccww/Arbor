from __future__ import annotations

from arbor.application.query_planner import plan_queries


def test_multihop_splits_on_and():
    planned = plan_queries(
        "What does 林夏 usually do on weekends and what pet does 林夏 keep?",
        "rules",
    )
    assert len(planned) >= 2
    joined = " ".join(item["query"] for item in planned)
    assert "weekend" in joined.lower() or "周末" in joined
    assert "pet" in joined.lower() or "宠物" in joined
