from __future__ import annotations

from arbor.domain.conversation.stream import parse_model_out


def test_parse_model_out_extracts_tool_calls():
    raw = '{"text": "", "citations": [], "tool_calls": [{"name": "calendar", "reason": "查日程"}]}'
    parsed = parse_model_out(raw)
    assert parsed["tool_calls"][0]["name"] == "calendar"
