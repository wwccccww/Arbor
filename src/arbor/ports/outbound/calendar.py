from __future__ import annotations

from typing import Protocol

from arbor.domain.shared.ids import TenantId, UserId


class CalendarTool(Protocol):
    def list_upcoming(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query_text: str,
    ) -> dict: ...
