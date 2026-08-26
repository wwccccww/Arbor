from __future__ import annotations

from typing import Protocol

from arbor.domain.shared.ids import TenantId, UserId


class TicketTool(Protocol):
    def create(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        title: str,
        description: str,
    ) -> dict: ...
