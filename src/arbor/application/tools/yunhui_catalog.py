"""Demo catalog for 云汇智选. Adapters wrap this when no mall URL is configured."""

from __future__ import annotations

_ORDERS = [
    {
        "order_id": "YH20260318001",
        "status": "shipped",
        "status_label": "已发货",
        "items": [
            {"sku": "YH-EP-01", "name": "云汇智选 降噪耳机", "qty": 1, "price_cents": 29900}
        ],
        "logistics": {"carrier": "顺丰", "tracking_no": "SF1234567890"},
    },
    {
        "order_id": "YH20260320014",
        "status": "paid",
        "status_label": "待发货",
        "items": [
            {"sku": "YH-KB-02", "name": "云汇智选 机械键盘", "qty": 1, "price_cents": 45900}
        ],
        "logistics": None,
    },
]

_PRODUCTS = [
    {
        "sku": "YH-EP-01",
        "name": "云汇智选 降噪耳机",
        "price_cents": 29900,
        "tags": ["耳机", "数码", "音频"],
    },
    {
        "sku": "YH-KB-02",
        "name": "云汇智选 机械键盘",
        "price_cents": 45900,
        "tags": ["键盘", "数码"],
    },
    {
        "sku": "YH-CUP-03",
        "name": "云汇智选 随行保温杯",
        "price_cents": 8900,
        "tags": ["杯", "日用"],
    },
]


def _matches(order: dict, query: str, order_id: str) -> bool:
    wanted = (order_id or "").strip().upper()
    if wanted:
        return str(order["order_id"]).upper() == wanted
    haystack = (query or "").strip()
    if not haystack:
        return True
    blob = " ".join(
        [str(order["order_id"]), str(order["status_label"])]
        + [str(item["name"]) for item in order["items"]]
    )
    return haystack in blob or haystack.upper() in blob


def demo_query_orders(*, query: str, order_id: str = "") -> dict:
    hits = [item for item in _ORDERS if _matches(item, query, order_id)]
    if not hits and (order_id or query):
        return {
            "tool": "order",
            "status": "ok",
            "provider": "stub",
            "mall": "云汇智选",
            "orders": [],
            "note": "演示库没有匹配订单。真实商城请配置 ARBOR_YUNHUI_API_URL",
        }
    return {
        "tool": "order",
        "status": "ok",
        "provider": "stub",
        "mall": "云汇智选",
        "orders": hits,
        "note": "演示订单（stub），未连接云汇智选",
    }


def demo_recommend_products(*, query: str, limit: int = 3) -> dict:
    text = (query or "").strip()
    ranked = list(_PRODUCTS)
    if text:
        ranked = [
            item
            for item in _PRODUCTS
            if text in item["name"] or any(text in tag for tag in item["tags"])
        ] or list(_PRODUCTS)
    picked = ranked[: max(1, min(int(limit or 3), 5))]
    return {
        "tool": "recommend",
        "status": "ok",
        "provider": "stub",
        "mall": "云汇智选",
        "products": picked,
        "note": "演示推荐（stub），未连接云汇智选",
    }


def demo_create_aftersale(*, order_id: str, reason: str, kind: str = "return") -> dict:
    order = (order_id or "").strip()
    if not order:
        return {
            "tool": "aftersale",
            "status": "error",
            "provider": "stub",
            "mall": "云汇智选",
            "note": "登记售后需要订单号",
        }
    labels = {"return": "退货", "refund": "退款", "exchange": "换货"}
    label = labels.get(kind, "退货")
    return {
        "tool": "aftersale",
        "status": "ok",
        "provider": "stub",
        "mall": "云汇智选",
        "aftersale_id": "stub-as-001",
        "order_id": order,
        "kind": kind or "return",
        "kind_label": label,
        "reason": (reason or "").strip()[:200],
        "note": f"演示{label}已登记（stub），未连接云汇智选",
    }
