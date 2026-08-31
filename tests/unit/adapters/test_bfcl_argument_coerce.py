from __future__ import annotations

from arbor.adapters.outbound.benchmarks.bfcl_loader import (
    coerce_tool_arguments,
    normalize_planner_tool_payload,
)


def test_coerce_tool_arguments_normalizes_date_and_number():
    schema = {
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["date", "limit"],
    }
    coerced = coerce_tool_arguments({"date": "2024/05/26", "limit": "3"}, schema)
    assert coerced["date"] == "2024-05-26"
    assert coerced["limit"] == 3


def test_normalize_planner_tool_payload_aliases():
    raw = normalize_planner_tool_payload(
        {
            "action": "function",
            "name": "search_calendar_events",
            "parameters": {"query": "event", "date": "2024-05-26"},
        }
    )
    assert raw["action"] == "tool"
    assert raw["tool_name"] == "search_calendar_events"
    assert raw["arguments"]["query"] == "event"
