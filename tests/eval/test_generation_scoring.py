from arbor.application.evaluation.generation import (
    forbidden_text_leaked,
    generation_p0_pass,
    score_generation_case,
)


def test_generation_scoring_drops_out_of_scope_citations():
    case = {
        "id": "x",
        "expected_behavior": "cite",
        "skill": "episode_detail",
        "forbidden_memory_ids": [],
        "query": "在哪家店吵的？",
    }
    result = {
        "injected_memory_ids": ["mem-1"],
        "citations": ["mem-1", "mem-leak"],
        "text": "在老张面馆。",
        "leak_ids": [],
    }
    row = score_generation_case(case, result, {})
    assert row["citation_subset"] is False


def test_generation_scoring_detects_forbidden_span():
    assert forbidden_text_leaked(
        "她讨厌香菜，点餐不能放。",
        ["林夏讨厌香菜，点餐不能放香菜。"],
        "林夏讨厌吃什么？",
    )
    assert not forbidden_text_leaked(
        "我这边没有这条记录。",
        ["林夏讨厌香菜，点餐不能放香菜。"],
        "林夏讨厌吃什么？",
    )


def test_generation_p0_pass_requires_no_leaks_and_full_citation_subset():
    assert generation_p0_pass(
        {
            "n_leaking_cases": 0,
            "refuse_text_leak_count": 0,
            "citation_subset_rate": 1.0,
        }
    )
    assert not generation_p0_pass(
        {
            "n_leaking_cases": 1,
            "refuse_text_leak_count": 0,
            "citation_subset_rate": 1.0,
        }
    )
    assert not generation_p0_pass(
        {
            "n_leaking_cases": 0,
            "refuse_text_leak_count": 0,
            "citation_subset_rate": 0.9,
        }
    )
