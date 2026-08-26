from __future__ import annotations

from arbor.application.tools.run_tools import run_persona_tools
from arbor.domain.persona.authorization import ToolPolicy
from arbor.domain.shared.ids import TenantId, UserId


class _RecordingCalendar:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def list_upcoming(self, *, tenant_id, user_id, query_text: str) -> dict:
        self.calls.append(
            {"tenant_id": tenant_id, "user_id": user_id, "query_text": query_text}
        )
        return {"tool": "calendar", "status": "ok", "provider": "test", "events": []}


def test_run_tools_uses_injected_calendar_tool():
    cal = _RecordingCalendar()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    results = run_persona_tools(
        "明天有什么日程安排？",
        ToolPolicy(allowed_tools=["calendar"], notes=""),
        tenant_id=tenant,
        user_id=user,
        calendar_tool=cal,
    )
    assert len(results) == 1
    assert results[0]["provider"] == "test"
    assert len(cal.calls) == 1
