from __future__ import annotations

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId


class EvalTicketTool:
    """Agent eval double: counts calls, flakes on titles containing 超时."""

    def __init__(self) -> None:
        self.create_calls = 0
        self._timeout_attempts: dict[str, int] = {}

    def create(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        title: str,
        description: str,
    ) -> dict:
        marker = f"{tenant_id.value}:{title or 'default'}"
        if "超时" in (title or ""):
            attempt = self._timeout_attempts.get(marker, 0)
            self._timeout_attempts[marker] = attempt + 1
            if attempt == 0:
                raise DomainError("TOOL_TIMEOUT", "simulated provider timeout")
        self.create_calls += 1
        return {
            "tool": "ticket",
            "status": "ok",
            "provider": "eval-ticket",
            "ticket_id": f"eval-{self.create_calls:03d}",
            "title": title or "用户反馈",
        }
