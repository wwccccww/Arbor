from __future__ import annotations

from arbor.domain.shared.ids import TenantId, UserId


class CountingTicketTool:
  """Test double that counts external ticket.create invocations."""

  def __init__(self) -> None:
    self.create_calls = 0

  def create(
      self,
      *,
      tenant_id: TenantId,
      user_id: UserId,
      title: str,
      description: str,
  ) -> dict:
    self.create_calls += 1
    return {
        "tool": "ticket",
        "status": "ok",
        "provider": "counting",
        "ticket_id": f"count-{self.create_calls:03d}",
        "title": title or "用户反馈",
    }
