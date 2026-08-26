from __future__ import annotations

from arbor.adapters.inbound.http.feishu_oauth import decode_oauth_state, encode_oauth_state
from arbor.adapters.outbound.tools.credential_store import InMemoryFeishuCredentialStore, FeishuUserTokens
from arbor.adapters.outbound.tools.feishu_calendar import FeishuCalendarTool
from arbor.domain.shared.ids import TenantId, UserId


class _FakeFeishuClient:
    def primary_calendar_id(self, user_access_token: str) -> str:
        assert user_access_token == "user-token"
        return "cal_primary"

    def list_events(self, user_access_token, calendar_id, *, start_time, end_time, page_size=10):
        assert calendar_id == "cal_primary"
        return [
            {
                "summary": "产品评审",
                "start_time": {"timestamp": "1609430400"},
                "description": "会议室 A",
            }
        ]

    def event_window(self, days: int = 7):
        return 1609430400, 1609516800

    def format_event(self, item):
        return {
            "title": item["summary"],
            "start": "2021-01-01T00:00:00+00:00",
            "note": item.get("description") or "",
        }


def test_feishu_oauth_state_roundtrip():
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    state = encode_oauth_state(tenant, user)
    got_tenant, got_user = decode_oauth_state(state)
    assert got_tenant == tenant
    assert got_user == user


def test_feishu_calendar_not_connected():
    tool = FeishuCalendarTool(_FakeFeishuClient(), InMemoryFeishuCredentialStore())
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    result = tool.list_upcoming(tenant_id=tenant, user_id=user, query_text="明天安排")
    assert result["status"] == "not_connected"
    assert result["provider"] == "feishu"


def test_feishu_calendar_lists_events():
    store = InMemoryFeishuCredentialStore()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    user = UserId("0a000000-0000-4000-a000-000000000002")
    store.save(
        tenant,
        user,
        FeishuUserTokens(
            access_token="user-token",
            refresh_token="refresh",
            expires_at=9999999999.0,
        ),
    )
    tool = FeishuCalendarTool(_FakeFeishuClient(), store)
    result = tool.list_upcoming(tenant_id=tenant, user_id=user, query_text="日程")
    assert result["status"] == "ok"
    assert result["provider"] == "feishu"
    assert len(result["events"]) == 1
    assert result["events"][0]["title"] == "产品评审"
