from __future__ import annotations

from typing import Protocol

from arbor.domain.shared.ids import TenantId, UserId


class YunhuiMall(Protocol):
    """Outbound port for the 云汇智选 mall."""

    def query_orders(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query: str,
        order_id: str = "",
    ) -> dict: ...

    def recommend_products(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query: str,
        limit: int = 3,
    ) -> dict: ...

    def create_aftersale(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        order_id: str,
        reason: str,
        kind: str = "return",
    ) -> dict: ...
