from arbor.adapters.outbound.inmemory import ScriptedLLM, _build_scripted_response, _is_fight_query


def test_fight_query_detection():
    assert _is_fight_query("我们上次为什么吵架？")
    assert not _is_fight_query("你好")


def test_scripted_fight_reply_with_citation():
    injected = ["0a000000-0000-4000-a000-000000000301", "0a000000-0000-4000-a000-000000000303"]
    out = _build_scripted_response("我们上次为什么吵架？", injected, None)
    assert "香菜" in out["text"]
    assert out["citations"] == ["0a000000-0000-4000-a000-000000000303"]


def test_scripted_fight_reply_without_memory():
    out = _build_scripted_response("我们上次为什么吵架？", ["0a000000-0000-4000-a000-000000000401"], None)
    assert "没有找到" in out["text"]
    assert out["citations"] == []


def test_scripted_llm_complete_fight():
    llm = ScriptedLLM()
    result = llm.complete(
        prompt_slots={},
        text="我们上次为什么吵架？",
        injected_memory_ids=["0a000000-0000-4000-a000-000000000303"],
    )
    assert result["citations"] == ["0a000000-0000-4000-a000-000000000303"]
