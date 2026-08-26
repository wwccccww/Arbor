from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger("arbor.feishu")

FEISHU_API = "https://open.feishu.cn/open-apis"


class FeishuError(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


@dataclass
class FeishuClient:
    app_id: str
    app_secret: str
    timeout: float = 15.0
    _app_access_token: str = ""
    _app_token_expires_at: float = 0.0

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        from urllib.parse import quote

        return (
            f"{FEISHU_API}/authen/v1/authorize"
            f"?app_id={quote(self.app_id)}"
            f"&redirect_uri={quote(redirect_uri, safe='')}"
            f"&state={quote(state)}"
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{FEISHU_API}{path}"
        response = httpx.request(
            method,
            url,
            headers=headers,
            json=json_body,
            params=params,
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except Exception as exc:
            raise FeishuError(-1, f"invalid response: {response.text[:200]}") from exc
        code = payload.get("code", -1)
        if code != 0:
            raise FeishuError(int(code), str(payload.get("msg") or "feishu error"))
        return payload.get("data") or {}

    def app_access_token(self) -> str:
        if self._app_access_token and time.time() < self._app_token_expires_at - 60:
            return self._app_access_token
        data = self._request(
            "POST",
            "/auth/v3/app_access_token/internal",
            json_body={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = str(data.get("app_access_token") or "")
        expire = int(data.get("expire") or 7200)
        if not token:
            raise FeishuError(-1, "missing app_access_token")
        self._app_access_token = token
        self._app_token_expires_at = time.time() + expire
        return token

    def exchange_code(self, code: str) -> dict[str, Any]:
        app_token = self.app_access_token()
        data = self._request(
            "POST",
            "/authen/v1/access_token",
            token=app_token,
            json_body={"grant_type": "authorization_code", "code": code},
        )
        return data

    def refresh_user_token(self, refresh_token: str) -> dict[str, Any]:
        app_token = self.app_access_token()
        data = self._request(
            "POST",
            "/authen/v1/refresh_access_token",
            token=app_token,
            json_body={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        return data

    def primary_calendar_id(self, user_access_token: str) -> str:
        data = self._request(
            "POST",
            "/calendar/v4/calendars/primary",
            token=user_access_token,
            json_body={},
        )
        calendar = data.get("calendar") or {}
        calendar_id = str(calendar.get("calendar_id") or "")
        if not calendar_id:
            raise FeishuError(-1, "missing calendar_id")
        return calendar_id

    def list_events(
        self,
        user_access_token: str,
        calendar_id: str,
        *,
        start_time: int,
        end_time: int,
        page_size: int = 10,
    ) -> list[dict]:
        data = self._request(
            "GET",
            f"/calendar/v4/calendars/{calendar_id}/events",
            token=user_access_token,
            params={
                "start_time": start_time,
                "end_time": end_time,
                "page_size": page_size,
            },
        )
        items = data.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def tokens_from_oauth(data: dict[str, Any]) -> tuple[str, str, float]:
        access = str(data.get("access_token") or "")
        refresh = str(data.get("refresh_token") or "")
        expires_in = int(data.get("expires_in") or data.get("expire") or 7200)
        if not access:
            raise FeishuError(-1, "missing user access_token")
        expires_at = time.time() + expires_in
        return access, refresh, expires_at

    @staticmethod
    def event_window(days: int = 7) -> tuple[int, int]:
        now = datetime.now(UTC)
        start = int(now.timestamp())
        end = int((now + timedelta(days=days)).timestamp())
        return start, end

    @staticmethod
    def format_event(item: dict) -> dict:
        summary = str(item.get("summary") or item.get("title") or "未命名日程")
        when = ""
        start = item.get("start_time")
        if isinstance(start, dict):
            ts = start.get("timestamp") or start.get("date")
            if ts:
                try:
                    when = datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
                except (TypeError, ValueError, OSError):
                    when = str(ts)
            else:
                when = str(start.get("date_time") or start.get("date") or "")
        elif start:
            try:
                when = datetime.fromtimestamp(int(start), tz=UTC).isoformat()
            except (TypeError, ValueError, OSError):
                when = str(start)
        return {
            "title": summary,
            "start": when,
            "note": str(item.get("description") or ""),
        }
