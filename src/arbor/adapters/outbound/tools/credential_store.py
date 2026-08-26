from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arbor.domain.shared.ids import TenantId, UserId


@dataclass
class FeishuUserTokens:
    access_token: str
    refresh_token: str
    expires_at: float
    calendar_id: str = ""

    def expired(self, skew_seconds: int = 60) -> bool:
        return time.time() >= (self.expires_at - skew_seconds)


class FeishuCredentialStore(Protocol):
    def get(self, tenant_id: TenantId, user_id: UserId) -> FeishuUserTokens | None: ...
    def save(self, tenant_id: TenantId, user_id: UserId, tokens: FeishuUserTokens) -> None: ...
    def delete(self, tenant_id: TenantId, user_id: UserId) -> None: ...


class InMemoryFeishuCredentialStore:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], FeishuUserTokens] = {}

    def get(self, tenant_id: TenantId, user_id: UserId) -> FeishuUserTokens | None:
        return self._data.get((tenant_id.value, user_id.value))

    def save(self, tenant_id: TenantId, user_id: UserId, tokens: FeishuUserTokens) -> None:
        self._data[(tenant_id.value, user_id.value)] = tokens

    def delete(self, tenant_id: TenantId, user_id: UserId) -> None:
        self._data.pop((tenant_id.value, user_id.value), None)


class FileFeishuCredentialStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, tenant_id: TenantId, user_id: UserId) -> Path:
        tenant_dir = self._root / tenant_id.value
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir / f"{user_id.value}.json"

    def get(self, tenant_id: TenantId, user_id: UserId) -> FeishuUserTokens | None:
        path = self._path(tenant_id, user_id)
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return FeishuUserTokens(
            access_token=raw["access_token"],
            refresh_token=raw["refresh_token"],
            expires_at=float(raw["expires_at"]),
            calendar_id=str(raw.get("calendar_id") or ""),
        )

    def save(self, tenant_id: TenantId, user_id: UserId, tokens: FeishuUserTokens) -> None:
        path = self._path(tenant_id, user_id)
        path.write_text(
            json.dumps(
                {
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_at": tokens.expires_at,
                    "calendar_id": tokens.calendar_id,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def delete(self, tenant_id: TenantId, user_id: UserId) -> None:
        path = self._path(tenant_id, user_id)
        if path.is_file():
            path.unlink()
