from __future__ import annotations

from arbor.application.tools.yunhui_catalog import (
    demo_create_aftersale,
    demo_query_orders,
    demo_recommend_products,
)
from arbor.domain.shared.ids import TenantId, UserId


class StubYunhuiMall:
    """Demo catalog used when 云汇智选 is not configured."""

    def query_orders(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query: str,
        order_id: str = "",
    ) -> dict:
        del tenant_id, user_id
        return demo_query_orders(query=query, order_id=order_id)

    def recommend_products(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query: str,
        limit: int = 3,
    ) -> dict:
        del tenant_id, user_id
        return demo_recommend_products(query=query, limit=limit)

    def create_aftersale(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        order_id: str,
        reason: str,
        kind: str = "return",
    ) -> dict:
        del tenant_id, user_id
        return demo_create_aftersale(order_id=order_id, reason=reason, kind=kind)
