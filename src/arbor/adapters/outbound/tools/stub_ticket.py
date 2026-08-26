from __future__ import annotations

from arbor.domain.shared.ids import TenantId, UserId


class StubTicketTool:
    def create(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        title: str,
        description: str,
    ) -> dict:
        return {
            "tool": "ticket",
            "status": "ok",
            "provider": "stub",
            "ticket_id": "stub-ticket-001",
            "title": title or "用户反馈",
            "note": "演示工单已登记（stub），未连接真实工单系统",
        }
