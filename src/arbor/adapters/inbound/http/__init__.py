from __future__ import annotations

from arbor.adapters.inbound.http.register_audit import register_audit_routes
from arbor.adapters.inbound.http.register_auth import register_auth_routes
from arbor.adapters.inbound.http.register_eval import register_eval_routes
from arbor.adapters.inbound.http.register_feishu import register_feishu_routes
from arbor.adapters.inbound.http.register_personas import register_persona_routes
from arbor.adapters.inbound.http.register_tenants import register_tenant_routes
from arbor.adapters.inbound.http.register_threads import register_thread_routes

__all__ = [
    "register_audit_routes",
    "register_auth_routes",
    "register_eval_routes",
    "register_persona_routes",
    "register_tenant_routes",
    "register_thread_routes",
]
