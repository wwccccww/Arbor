from __future__ import annotations

import secrets
from typing import Protocol


class AuthSessionStore(Protocol):
    def issue(self, profile: dict) -> dict: ...
    def get_profile(self, access_token: str) -> dict | None: ...
    def refresh_session(self, refresh_token: str) -> dict | None: ...
    def logout(self, refresh_token: str) -> None: ...


class InMemoryAuthSessionStore:
    def __init__(self, static_tokens: dict[str, dict] | None = None) -> None:
        self._access: dict[str, dict] = {k: dict(v) for k, v in (static_tokens or {}).items()}
        self._refresh: dict[str, str] = {}

    def issue(self, profile: dict) -> dict:
        access = f"tok_{secrets.token_urlsafe(16)}"
        refresh = f"ref_{secrets.token_urlsafe(16)}"
        stored = dict(profile)
        self._access[access] = stored
        self._refresh[refresh] = access
        return {
            "access_token": access,
            "refresh_token": refresh,
            "user": {"id": stored["user_id"], "email": stored["email"]},
        }

    def get_profile(self, access_token: str) -> dict | None:
        profile = self._access.get(access_token)
        return dict(profile) if profile is not None else None

    def refresh_session(self, refresh_token: str) -> dict | None:
        access = self._refresh.get(refresh_token)
        profile = self._access.get(access) if access else None
        if not access or not profile:
            return None
        self._refresh.pop(refresh_token, None)
        self._access.pop(access, None)
        return self.issue(profile)

    def logout(self, refresh_token: str) -> None:
        access = self._refresh.pop(refresh_token, None)
        if access:
            self._access.pop(access, None)
