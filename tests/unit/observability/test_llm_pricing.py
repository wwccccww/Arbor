from __future__ import annotations

from arbor.observability.llm_pricing import estimated_llm_cost_usd


def test_estimated_llm_cost_usd_defaults():
    cost = estimated_llm_cost_usd(model="deepseek-chat", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost > 0


def test_estimated_llm_cost_usd_env_override(monkeypatch):
    monkeypatch.setenv("ARBOR_LLM_PRICE_DEEPSEEK_CHAT_INPUT", "1.0")
    monkeypatch.setenv("ARBOR_LLM_PRICE_DEEPSEEK_CHAT_OUTPUT", "2.0")
    cost = estimated_llm_cost_usd(model="deepseek-chat", input_tokens=1_000_000, output_tokens=500_000)
    assert cost == 2.0
