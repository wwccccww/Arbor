from __future__ import annotations

import json
from pathlib import Path

from arbor.adapters.outbound.deepseek.chat import _system_prompt, eval_generation_retry_hint
from arbor.application.evaluation.ragas_tuning import (
    EVOLUTION_SINGLE,
    aggregate_generation_by_evolution,
    build_ragas_report_extras,
    resolve_retrieval_config,
    run_ragas_retrieval_ablation,
    select_ragas_cases,
    worst_ragas_cases,
)
from arbor.application.retrieval_config import RetrievalConfig


def test_resolve_retrieval_config_tuned_differs_from_default():
    tuned = resolve_retrieval_config("tuned")
    default = resolve_retrieval_config("default")
    assert tuned.prompt_k == 5
    assert tuned.mmr_lambda == 0.85
    assert default.prompt_k != tuned.prompt_k or default.mmr_lambda != tuned.mmr_lambda


def test_retrieval_config_ragas_tuned_factory():
    cfg = RetrievalConfig.ragas_tuned()
    assert cfg.rerank_k == 4
    assert cfg.pool_k == 20


def test_aggregate_generation_by_evolution():
    rows = [
        {
            "id": "a",
            "behavior": "answer",
            "evolution_label": "single_hop",
            "citation_subset": True,
            "text_leak": False,
            "retrieval_leak": False,
            "leaked": False,
            "ragas_faithfulness": 0.9,
            "ragas_context_recall": 0.8,
            "ragas_context_precision": 0.4,
            "ragas_answer_relevancy": 0.2,
            "ragas_answer_correctness": 0.7,
        },
        {
            "id": "b",
            "behavior": "answer",
            "evolution_label": "multi_hop",
            "citation_subset": True,
            "text_leak": False,
            "retrieval_leak": False,
            "leaked": False,
            "ragas_faithfulness": 0.5,
            "ragas_context_recall": 0.5,
            "ragas_context_precision": 0.2,
            "ragas_answer_relevancy": 0.1,
            "ragas_answer_correctness": 0.4,
        },
    ]
    by_evo = aggregate_generation_by_evolution(rows)
    assert set(by_evo) == {"multi_hop", "single_hop"}
    assert by_evo["single_hop"]["ragas_faithfulness"] == 0.9


def test_worst_ragas_cases_orders_by_primary_avg():
    rows = [
        {
            "id": "good",
            "behavior": "answer",
            "evolution_label": "single_hop",
            "leaked": False,
            "query": "q1",
            "reference": "r1",
            "text": "a1",
            "ragas_faithfulness": 0.9,
            "ragas_context_recall": 0.9,
            "ragas_context_precision": 0.9,
            "ragas_answer_correctness": 0.9,
            "ragas_answer_relevancy": 0.1,
        },
        {
            "id": "bad",
            "behavior": "answer",
            "evolution_label": "multi_hop",
            "leaked": False,
            "query": "q2",
            "reference": "r2",
            "text": "a2",
            "ragas_faithfulness": 0.2,
            "ragas_context_recall": 0.2,
            "ragas_context_precision": 0.2,
            "ragas_answer_correctness": 0.2,
            "ragas_answer_relevancy": 0.1,
        },
    ]
    worst = worst_ragas_cases(rows, limit=1)
    assert worst[0]["id"] == "bad"


def test_build_ragas_report_extras():
    case_index = {
        "c1": {
            "id": "c1",
            "query": "q",
            "reference": "r",
            "evolution_type": EVOLUTION_SINGLE,
        }
    }
    rows = [
        {
            "id": "c1",
            "behavior": "answer",
            "citation_subset": True,
            "text_leak": False,
            "retrieval_leak": False,
            "leaked": False,
            "text": "ans",
            "ragas_faithfulness": 1.0,
            "ragas_context_recall": 1.0,
            "ragas_context_precision": 1.0,
            "ragas_answer_relevancy": 0.2,
            "ragas_answer_correctness": 1.0,
        }
    ]
    extras = build_ragas_report_extras(rows, case_index=case_index, worst_n=5)
    assert "single_hop" in extras["by_evolution"]
    assert extras["reference_metrics"] == ["ragas_answer_relevancy"]
    assert extras["worst_cases"][0]["id"] == "c1"


def test_eval_generation_retry_hint():
    assert "为空" in (eval_generation_retry_hint("q", "") or "")
    assert "英文" in (
        eval_generation_retry_hint("Where does Lin Xia reside in Hangzhou?", "林夏住在杭州西湖区。") or ""
    )
    assert eval_generation_retry_hint("Where does Lin Xia reside?", "Lin Xia lives in Hangzhou.") is None


def test_deepseek_chat_keeps_capture_usage():
    from arbor.adapters.outbound.deepseek.chat import DeepSeekChatLLM

    assert callable(DeepSeekChatLLM._capture_usage)


def test_eval_generation_system_prompt():
    prompt = _system_prompt({"profile": {"display_name": "林夏"}, "eval_generation_mode": True}, [])
    assert "评测模式" in prompt
    assert "第三人称" in prompt
    assert "taboos" in prompt
    assert "citations" in prompt
    assert "回答语言必须与用户问题一致" in prompt
    assert "免责句" in prompt
    assert "记忆 JSON" in prompt
    assert "英文问题的 text 必须是英文句子" in prompt
    assert "工单客户名" in prompt


def test_select_ragas_cases_stratified_balances_hops():
    cases = json.loads(
        (Path(__file__).resolve().parents[3] / "eval/fixtures/suite-ragas-official/cases.json").read_text(
            encoding="utf-8"
        )
    )
    subset = select_ragas_cases(cases, limit=20, stratified=True)
    assert len(subset) == 20
    singles = sum(1 for case in subset if "single" in str(case.get("evolution_type", "")))
    multis = len(subset) - singles
    assert singles == 10
    assert multis == 10


def test_select_ragas_cases_head_limit():
    cases = [{"id": f"c{i}", "evolution_type": EVOLUTION_SINGLE} for i in range(5)]
    assert len(select_ragas_cases(cases, limit=3, stratified=False)) == 3


def test_retrieval_ablation_runs_on_fixture():
    table = run_ragas_retrieval_ablation(backend="memory", embed="fixture")
    assert set(table) == {"default", "tuned"}
    for arm in table.values():
        assert arm["n_cases"] == 100
        assert arm["tenant_leak_count"] == 0
