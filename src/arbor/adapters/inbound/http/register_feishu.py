from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Header
from fastapi.responses import RedirectResponse

from arbor.adapters.inbound.http.feishu_oauth import decode_oauth_state, encode_oauth_state
from arbor.adapters.outbound.tools.credential_store import FeishuCredentialStore, FeishuUserTokens
from arbor.adapters.outbound.tools.feishu_client import FeishuClient, FeishuError
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId


@dataclass
class FeishuHttpDeps:
    client: FeishuClient
    credentials: FeishuCredentialStore
    redirect_uri: str
    success_url: str
    current_user: Callable


def register_feishu_routes(app, deps: FeishuHttpDeps) -> None:
    @app.get("/v1/me/feishu/status")
    def feishu_status(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant = TenantId(x_tenant_id)
        actor = UserId(user["user_id"])
        tokens = deps.credentials.get(tenant, actor)
        return {
            "connected": tokens is not None,
            "provider": "feishu",
            "calendar_id": tokens.calendar_id if tokens else "",
        }

    @app.get("/v1/me/feishu/connect")
    def feishu_connect(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        tenant = TenantId(x_tenant_id)
        actor = UserId(user["user_id"])
        state = encode_oauth_state(tenant, actor)
        url = deps.client.authorize_url(deps.redirect_uri, state)
        return {"authorize_url": url, "provider": "feishu"}

    @app.delete("/v1/me/feishu/disconnect", status_code=204)
    def feishu_disconnect(
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        deps.credentials.delete(TenantId(x_tenant_id), UserId(user["user_id"]))

    @app.get("/v1/auth/feishu/callback")
    def feishu_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ):
        if error:
            return RedirectResponse(f"{deps.success_url}?feishu=error&reason={error}")
        if not code or not state:
            raise DomainError("VALIDATION_ERROR", "missing code or state")
        tenant_id, user_id = decode_oauth_state(state)
        try:
            data = deps.client.exchange_code(code)
            access, refresh, expires_at = deps.client.tokens_from_oauth(data)
            deps.credentials.save(
                tenant_id,
                user_id,
                FeishuUserTokens(
                    access_token=access,
                    refresh_token=refresh,
                    expires_at=expires_at,
                ),
            )
        except FeishuError as exc:
            return RedirectResponse(
                f"{deps.success_url}?feishu=error&code={exc.code}&msg={exc.msg[:80]}"
            )
        return RedirectResponse(f"{deps.success_url}?feishu=connected")
