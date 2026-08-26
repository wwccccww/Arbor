from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header

from arbor.adapters.inbound.http.schemas import LoginIn, LogoutIn, RefreshIn
from arbor.adapters.inbound.http.serialization import tenant_json
from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import UserId


@dataclass
class AuthHttpDeps:
    users: object
    tenants: object
    list_tenants: Callable
    authenticate_user: Callable
    profile_for_demo_email: Callable
    demo_password_ok: Callable
    current_user: Callable


def register_auth_routes(app, deps: AuthHttpDeps) -> None:
    @app.post("/v1/auth/login")
    def login(payload: LoginIn):
        email = (payload.email or "").strip().lower()
        profile = deps.authenticate_user(deps.users, deps.tenants, email, payload.password)
        if profile is None:
            profile = deps.profile_for_demo_email(email)
            if profile is None or not deps.demo_password_ok(email, payload.password):
                raise DomainError("UNAUTHENTICATED", "bad credentials")
        return app.state.auth_sessions.issue(profile)

    @app.post("/v1/auth/refresh")
    def refresh(payload: RefreshIn):
        tokens = app.state.auth_sessions.refresh_session(payload.refresh_token)
        if tokens is None:
            raise DomainError("UNAUTHENTICATED", "bad refresh token")
        return tokens

    @app.post("/v1/auth/logout")
    def logout(payload: LogoutIn | None = None):
        token = (payload.refresh_token if payload else "") or ""
        app.state.auth_sessions.logout(token)
        return {"ok": True}

    @app.get("/v1/me")
    def me(authorization: str | None = Header(default=None)):
        user = deps.current_user(authorization)
        actor = UserId(user["user_id"])
        return {
            "user": {"id": user["user_id"], "email": user["email"]},
            "tenants": [tenant_json(item, actor) for item in deps.list_tenants(user_id=actor)],
            "runtime": app.state.runtime,
        }
