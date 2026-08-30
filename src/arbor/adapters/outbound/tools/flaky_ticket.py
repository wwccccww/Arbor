from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId


class FlakyTicketTool:
    """Test double: first attempt per title raises TOOL_TIMEOUT, retry succeeds once."""

    def __init__(self) -> None:
        self._attempts: dict[str, int] = {}
        self.create_calls = 0

    def create(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        title: str,
        description: str,
    ) -> dict:
        marker = f"{tenant_id.value}:{title or 'default'}"
        attempt = self._attempts.get(marker, 0)
        self._attempts[marker] = attempt + 1
        if attempt == 0:
            raise DomainError("TOOL_TIMEOUT", "simulated provider timeout")
        self.create_calls += 1
        return {
            "tool": "ticket",
            "status": "ok",
            "provider": "flaky",
            "ticket_id": f"flaky-{self.create_calls:03d}",
            "title": title or "用户反馈",
        }
