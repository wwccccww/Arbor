from __future__ import annotations

from arbor.application.evaluation.generation import injected_contexts, strip_eval_hedges, trim_ragas_contexts


def test_trim_ragas_contexts_keeps_cited_and_reference_overlap():
    prompt_slots = {
        "profile": {"display_name": "林夏"},
        "event_hits": [{"title": "面店争吵", "summary": "因香菜吵架"}],
        "memory_hits": [
            {"id": "mem-a", "text": "林夏住在杭州西湖区。"},
            {"id": "mem-b", "text": "和好后约定每周日晚上 21:00 打电话。"},
        ],
    }
    raw = injected_contexts(prompt_slots)
    trimmed = trim_ragas_contexts(
        raw,
        citations=["mem-a"],
        reference_contexts=["林夏住在杭州西湖区。"],
        max_memories=2,
    )
    assert any("mem-a" in line for line in trimmed)
    assert not any("mem-b" in line for line in trimmed)
    assert trimmed[0].startswith("记忆 mem-a")
    assert not any(line.startswith("档案:") for line in trimmed)


def test_trim_ragas_contexts_falls_back_when_empty():
    raw = ["记忆 mem-a: unrelated", "记忆 mem-b: also unrelated"]
    trimmed = trim_ragas_contexts(
        raw,
        citations=[],
        reference_contexts=["totally different"],
        max_memories=1,
    )
    assert len(trimmed) == 1


def test_trim_ragas_contexts_keeps_answer_overlap():
    raw = [
        "记忆 mem-a: 林夏住在杭州西湖区。",
        "记忆 mem-b: 无关内容。",
    ]
    trimmed = trim_ragas_contexts(
        raw,
        citations=[],
        reference_contexts=[],
        answer="林夏住在杭州西湖区。",
        max_memories=1,
    )
    assert any("mem-a" in line for line in trimmed)
    assert not any("mem-b" in line for line in trimmed)


def test_trim_ragas_contexts_drops_display_name_only_profile():
    raw = [
        "档案: display_name=林夏",
        "记忆 mem-a: 和好后约定每周日晚上 21:00 打电话。",
        "记忆 mem-b: unrelated noise",
    ]
    trimmed = trim_ragas_contexts(
        raw,
        citations=["mem-a"],
        reference_contexts=["和好后约定每周日晚上 21:00 打电话。"],
        answer="林夏和好后约定每周日晚上 21:00 打电话。",
        max_memories=1,
    )
    assert trimmed[0].startswith("记忆 mem-a")
    assert not any(line.startswith("档案:") for line in trimmed)
    assert not any("mem-b" in line for line in trimmed)


def test_trim_ragas_contexts_keeps_profile_with_taboos():
    raw = [
        "档案: display_name=林夏 taboos=['香菜']",
        "记忆 mem-a: 林夏讨厌香菜。",
    ]
    trimmed = trim_ragas_contexts(
        raw,
        citations=["mem-a"],
        reference_contexts=["林夏讨厌香菜。"],
        answer="林夏讨厌香菜。",
        max_memories=1,
    )
    assert any(line.startswith("档案:") for line in trimmed)
    assert trimmed[-1].startswith("档案:")


def test_trim_ragas_contexts_ranks_reference_memory_before_noise():
    raw = [
        "档案: display_name=林夏",
        "记忆 mem-noise: 林夏很喜欢猫。",
        "记忆 mem-hit: 林夏住在杭州西湖区。",
        "事件: 无关事件 其他事情。",
    ]
    trimmed = trim_ragas_contexts(
        raw,
        citations=["mem-hit"],
        reference_contexts=["林夏住在杭州西湖区。"],
        answer="林夏住在杭州西湖区。",
        max_memories=2,
        max_events=1,
    )
    assert trimmed[0].startswith("记忆 mem-hit")
    assert not any(line.startswith("档案:") for line in trimmed)


def test_strip_eval_hedges_drops_not_mentioned_clause():
    text = "工单 #8842 已升级，承诺三日内补发充电器，但现有信息未提及发票相关安排。"
    assert "未提及" not in strip_eval_hedges(text)
    assert "补发充电器" in strip_eval_hedges(text)
