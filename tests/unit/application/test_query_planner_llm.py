from __future__ import annotations

from arbor.application.query_planner import _parse_llm_plan, plan_queries


def test_plan_queries_llm_mode_parses_json_array():
    raw = '[{"query": "林夏住哪里", "intent": "profile"}, {"query": "面店吵架", "intent": "episode"}]'
    planned = _parse_llm_plan(raw, "fallback")
    assert len(planned) == 2
    assert planned[0]["intent"] == "profile"


def test_plan_queries_llm_falls_back_to_rules_without_api():
    planned = plan_queries("因为面店吵架，后来怎么样了？", "llm")
    assert len(planned) >= 2
