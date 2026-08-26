from __future__ import annotations

from datetime import UTC, datetime

from arbor.adapters.outbound.tools.credential_store import FeishuCredentialStore, FeishuUserTokens
from arbor.adapters.outbound.tools.feishu_client import FeishuClient, FeishuError
from arbor.domain.shared.ids import TenantId, UserId


class StubCalendarTool:
    def list_upcoming(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query_text: str,
    ) -> dict:
        now = datetime.now(UTC)
        return {
            "tool": "calendar",
            "status": "ok",
            "provider": "stub",
            "summary": "演示日程（stub）",
            "events": [
                {
                    "title": "与用户视频通话",
                    "start": now.replace(hour=20, minute=0, second=0, microsecond=0).isoformat(),
                    "note": "本地 stub，未连接真实日历 API",
                }
            ],
        }


class FeishuCalendarTool:
    def __init__(self, client: FeishuClient, credentials: FeishuCredentialStore) -> None:
        self._client = client
        self._credentials = credentials

    def list_upcoming(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        query_text: str,
    ) -> dict:
        stored = self._credentials.get(tenant_id, user_id)
        if stored is None:
            return {
                "tool": "calendar",
                "status": "not_connected",
                "provider": "feishu",
                "summary": "未绑定飞书日历",
                "events": [],
                "note": "请先在设置中连接飞书账号（GET /v1/me/feishu/connect）",
            }
        try:
            access = self._ensure_access_token(tenant_id, user_id, stored)
            calendar_id = stored.calendar_id or self._client.primary_calendar_id(access)
            if calendar_id != stored.calendar_id:
                stored.calendar_id = calendar_id
                self._credentials.save(tenant_id, user_id, stored)
            start, end = self._client.event_window(days=7)
            raw_events = self._client.list_events(
                access,
                calendar_id,
                start_time=start,
                end_time=end,
                page_size=10,
            )
            events = [self._client.format_event(item) for item in raw_events]
            return {
                "tool": "calendar",
                "status": "ok",
                "provider": "feishu",
                "summary": f"飞书近 7 日日程（{len(events)} 条）",
                "events": events,
            }
        except FeishuError as exc:
            return {
                "tool": "calendar",
                "status": "error",
                "provider": "feishu",
                "summary": "飞书日历查询失败",
                "events": [],
                "note": exc.msg,
                "code": exc.code,
            }

    def _ensure_access_token(
        self,
        tenant_id: TenantId,
        user_id: UserId,
        stored: FeishuUserTokens,
    ) -> str:
        if not stored.expired():
            return stored.access_token
        data = self._client.refresh_user_token(stored.refresh_token)
        access, refresh, expires_at = self._client.tokens_from_oauth(data)
        updated = FeishuUserTokens(
            access_token=access,
            refresh_token=refresh or stored.refresh_token,
            expires_at=expires_at,
            calendar_id=stored.calendar_id,
        )
        self._credentials.save(tenant_id, user_id, updated)
        return updated.access_token
