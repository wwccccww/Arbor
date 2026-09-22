from __future__ import annotations

import httpx

from arbor.domain.shared.ids import TenantId, UserId


class HttpYunhuiMall:
    """Call a 云汇智选-compatible HTTP API.

    ``api_url`` is the API root. Arbor posts:
    - ``{root}/orders/query``
    - ``{root}/products/recommend``
    - ``{root}/aftersales``
    """

    def __init__(self, api_url: str, api_key: str = "", timeout: float = 15.0) -> None:
        self._root = api_url.strip().rstrip("/")
        self._api_key = api_key.strip()
        self._timeout = timeout

    def query_orders(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query: str,
        order_id: str = "",
    ) -> dict:
        body = self._post(
            "/orders/query",
            {
                "tenant_id": tenant_id.value,
                "user_id": user_id.value,
                "query": query,
                "order_id": order_id,
                "source": "arbor-chat",
            },
        )
        if body.get("status") == "error":
            body["tool"] = "order"
            return body
        orders = body.get("orders") or body.get("data", {}).get("orders") or []
        return {
            "tool": "order",
            "status": "ok",
            "provider": "http",
            "mall": "云汇智选",
            "orders": orders,
            "note": str(body.get("note") or "已从云汇智选查询订单"),
        }

    def recommend_products(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query: str,
        limit: int = 3,
    ) -> dict:
        body = self._post(
            "/products/recommend",
            {
                "tenant_id": tenant_id.value,
                "user_id": user_id.value,
                "query": query,
                "limit": limit,
                "source": "arbor-chat",
            },
        )
        if body.get("status") == "error":
            body["tool"] = "recommend"
            return body
        products = body.get("products") or body.get("data", {}).get("products") or []
        return {
            "tool": "recommend",
            "status": "ok",
            "provider": "http",
            "mall": "云汇智选",
            "products": products,
            "note": str(body.get("note") or "已从云汇智选获取推荐"),
        }

    def create_aftersale(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        order_id: str,
        reason: str,
        kind: str = "return",
    ) -> dict:
        body = self._post(
            "/aftersales",
            {
                "tenant_id": tenant_id.value,
                "user_id": user_id.value,
                "order_id": order_id,
                "reason": reason,
                "kind": kind or "return",
                "source": "arbor-chat",
            },
        )
        if body.get("status") == "error":
            body["tool"] = "aftersale"
            return body
        aftersale_id = (
            body.get("id")
            or body.get("aftersale_id")
            or body.get("data", {}).get("id")
            or body.get("data", {}).get("aftersale_id")
        )
        return {
            "tool": "aftersale",
            "status": "ok",
            "provider": "http",
            "mall": "云汇智选",
            "aftersale_id": str(aftersale_id or "unknown"),
            "order_id": order_id,
            "kind": kind or "return",
            "note": str(body.get("note") or "已提交至云汇智选售后"),
        }

    def _post(self, path: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = httpx.post(
                f"{self._root}{path}",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return {
                "status": "error",
                "provider": "http",
                "mall": "云汇智选",
                "note": f"云汇智选 API 请求失败: {exc}",
            }
        if response.status_code >= 400:
            return {
                "status": "error",
                "provider": "http",
                "mall": "云汇智选",
                "note": f"云汇智选 API HTTP {response.status_code}",
            }
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            return {}
        return body


def build_yunhui_mall():
    from arbor.adapters.outbound.tools.stub_yunhui import StubYunhuiMall
    from arbor.env import yunhui_api_key, yunhui_api_url, yunhui_backend

    backend = yunhui_backend()
    url = yunhui_api_url()
    if (backend == "http" or (backend == "auto" and url)) and url:
        return HttpYunhuiMall(api_url=url, api_key=yunhui_api_key())
    return StubYunhuiMall()
