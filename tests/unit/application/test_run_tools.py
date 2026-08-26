from __future__ import annotations

import re

from arbor.application.tools.run_tools import run_persona_tools
from arbor.domain.persona.authorization import ToolPolicy


def test_calendar_tool_runs_when_allowed_and_triggered():
    results = run_persona_tools(
        "明天有什么日程安排？",
        ToolPolicy(allowed_tools=["calendar"], notes=""),
    )
    assert len(results) == 1
    assert results[0]["tool"] == "calendar"
    assert results[0]["status"] == "ok"


def test_ticket_tool_skipped_when_not_allowed():
    results = run_persona_tools(
        "帮我开个工单报修",
        ToolPolicy(allowed_tools=["calendar"], notes=""),
    )
    assert results == []


def test_ticket_tool_runs_with_alias():
    results = run_persona_tools(
        "空调坏了需要报修",
        ToolPolicy(allowed_tools=["ticket"], notes=""),
    )
    assert len(results) == 1
    assert results[0]["tool"] == "ticket"
    assert "stub-ticket" in results[0]["ticket_id"]
