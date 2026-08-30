from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header
from fastapi.responses import Response

from arbor.domain.errors import DomainError
from arbor.observability.runtime import check_readiness, probe_dependencies


@dataclass
class ObservabilityHttpDeps:
    observability: object
    runtime: dict
    database_url: str | None
    redis_url: str | None
    object_store_backend: str
    decision_traces: object | None
    current_user: Callable
    workspace_admin_for: Callable


def register_observability_routes(app, deps: ObservabilityHttpDeps) -> None:
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        probes = probe_dependencies(None)
        body = check_readiness(
            database_url_configured=deps.database_url,
            redis_url_configured=deps.redis_url,
            object_store_backend=deps.object_store_backend,
            postgres_reachable=probes.get("postgres"),
            redis_reachable=probes.get("redis"),
        )
        for name, item in body["checks"].items():
            deps.observability.set_gauge(
                "arbor_dependency_up",
                1.0 if item.get("ok") else 0.0,
                dependency=name,
            )
        status = 200 if body["ready"] else 503
        return Response(
            content=__import__("json").dumps(body, ensure_ascii=False),
            media_type="application/json",
            status_code=status,
        )

    @app.get("/metrics")
    def metrics():
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            from arbor.observability.metrics import prometheus_registry

            registry = prometheus_registry()
            payload = generate_latest(registry) if registry is not None else generate_latest()
            return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
        except ImportError:
            return Response(
                content="prometheus_client not installed\n",
                media_type="text/plain",
                status_code=503,
            )

    @app.get("/v1/debug/requests/{request_id}")
    def get_debug_request(
        request_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if not deps.workspace_admin_for(user, x_tenant_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        if deps.decision_traces is None:
            raise DomainError("NOT_FOUND", "trace not found")
        entry = deps.decision_traces.get_by_request_id(x_tenant_id, request_id)
        if entry is None:
            raise DomainError("NOT_FOUND", "trace not found")
        return {
            "request_id": entry["request_id"],
            "tenant_id": entry["tenant_id"],
            "persona_id": entry.get("persona_id"),
            "thread_id": entry.get("thread_id"),
            "message_id": entry.get("message_id"),
            "created_at": entry.get("created_at"),
            "expires_at": entry.get("expires_at"),
            "decision_trace": entry.get("summary_json") or {},
        }
