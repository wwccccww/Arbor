from __future__ import annotations

from arbor.application.evaluation.generation import injected_contexts, trim_ragas_contexts


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
