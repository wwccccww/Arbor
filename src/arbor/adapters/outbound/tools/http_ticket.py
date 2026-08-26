from __future__ import annotations

import httpx

from arbor.domain.shared.ids import TenantId, UserId


class HttpTicketTool:
    def __init__(self, api_url: str, api_key: str = "", timeout: float = 15.0) -> None:
        self._url = api_url.strip()
        self._api_key = api_key.strip()
        self._timeout = timeout

    def create(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        title: str,
        description: str,
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "tenant_id": tenant_id.value,
            "user_id": user_id.value,
            "title": title,
            "description": description,
            "source": "arbor-chat",
        }
        try:
            response = httpx.post(self._url, json=payload, headers=headers, timeout=self._timeout)
        except httpx.HTTPError as exc:
            return {
                "tool": "ticket",
                "status": "error",
                "provider": "http",
                "note": f"工单 API 请求失败: {exc}",
            }
        if response.status_code >= 400:
            return {
                "tool": "ticket",
                "status": "error",
                "provider": "http",
                "note": f"工单 API HTTP {response.status_code}",
            }
        try:
            body = response.json()
        except ValueError:
            body = {}
        ticket_id = (
            body.get("id")
            or body.get("ticket_id")
            or body.get("data", {}).get("id")
            or body.get("data", {}).get("ticket_id")
        )
        return {
            "tool": "ticket",
            "status": "ok",
            "provider": "http",
            "ticket_id": str(ticket_id or "unknown"),
            "title": title,
            "note": "已提交至工单系统",
        }
