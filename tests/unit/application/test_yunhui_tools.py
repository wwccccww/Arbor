from __future__ import annotations

from unittest.mock import MagicMock, patch

from arbor.adapters.outbound.tools.http_yunhui import HttpYunhuiMall
from arbor.application.tools.execute import execute_tool_calls
from arbor.application.tools.run_tools import run_persona_tools
from arbor.domain.persona.authorization import ToolPolicy
from arbor.domain.shared.ids import TenantId, UserId


def test_order_tool_returns_demo_shipment():
    results = run_persona_tools(
        "查一下订单 YH20260318001 的物流",
        ToolPolicy(allowed_tools=["order"], notes=""),
    )
    assert len(results) == 1
    assert results[0]["tool"] == "order"
    assert results[0]["orders"][0]["status_label"] == "已发货"
    assert results[0]["orders"][0]["items"][0]["name"] == "云汇智选 降噪耳机"


def test_recommend_tool_filters_catalog():
    results = run_persona_tools(
        "推荐一款耳机",
        ToolPolicy(allowed_tools=["recommend"], notes=""),
    )
    assert results[0]["tool"] == "recommend"
    assert any("耳机" in item["name"] for item in results[0]["products"])


def test_aftersale_requires_order_id():
    missing = run_persona_tools(
        "我要退货",
        ToolPolicy(allowed_tools=["aftersale"], notes=""),
    )
    assert missing[0]["status"] == "error"
    created = run_persona_tools(
        "订单 YH20260318001 申请退款",
        ToolPolicy(allowed_tools=["aftersale"], notes=""),
    )
    assert created[0]["status"] == "ok"
    assert created[0]["kind"] == "refund"
    assert created[0]["aftersale_id"] == "stub-as-001"


def test_mall_tools_skipped_when_not_allowed():
    results = run_persona_tools(
        "查一下订单 YH20260318001",
        ToolPolicy(allowed_tools=["ticket"], notes=""),
    )
    assert results == []


def test_http_yunhui_maps_order_payload():
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"orders": [{"order_id": "YH1", "status_label": "已签收"}]}
    with patch("httpx.post", return_value=response) as post:
        result = HttpYunhuiMall("https://mall.example.com/api").query_orders(
            tenant_id=tenant,
            user_id=user,
            query="耳机",
            order_id="YH1",
        )
    assert post.call_args.args[0] == "https://mall.example.com/api/orders/query"
    assert result["orders"][0]["order_id"] == "YH1"


def test_execute_tool_calls_recommend():
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    results = execute_tool_calls(
        [{"name": "recommend", "reason": "耳机"}],
        allowed_tools={"recommend"},
        tenant_id=tenant,
        user_id=user,
        query_text="推荐耳机",
    )
    assert results[0]["tool"] == "recommend"
    assert results[0]["products"]
