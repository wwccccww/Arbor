from __future__ import annotations

from unittest.mock import MagicMock, patch

from arbor.adapters.outbound.tools.http_ticket import HttpTicketTool
from arbor.application.tools.execute import execute_tool_calls
from arbor.domain.shared.ids import TenantId, UserId


def test_http_ticket_maps_response_id():
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "TKT-99"}
    with patch("httpx.post", return_value=response) as post:
        result = HttpTicketTool("https://tickets.example.com/api").create(
            tenant_id=tenant,
            user_id=user,
            title="空调故障",
            description="空调坏了",
        )
    post.assert_called_once()
    assert result["ticket_id"] == "TKT-99"
    assert result["status"] == "ok"


def test_execute_tool_calls_ticket():
    ticket = MagicMock()
    ticket.create.return_value = {"tool": "ticket", "status": "ok", "ticket_id": "T1"}
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    results = execute_tool_calls(
        [{"name": "ticket", "reason": "报修"}],
        allowed_tools={"ticket"},
        tenant_id=tenant,
        user_id=user,
        query_text="空调坏了",
        ticket_tool=ticket,
    )
    assert len(results) == 1
    ticket.create.assert_called_once()
