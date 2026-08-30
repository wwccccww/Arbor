from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Header
from fastapi.responses import Response

from arbor.domain.errors import DomainError
from arbor.domain.shared.ids import TenantId, UserId
from arbor.observability.gauges import refresh_operational_gauges
from arbor.observability.runtime import check_readiness, probe_dependencies
from arbor.observability.sampling import decrypt_payload


@dataclass
class ObservabilityHttpDeps:
    observability: object
    runtime: dict
    database_url: str | None
    redis_url: str | None
    object_store_backend: str
    decision_traces: object | None
    inbox: object | None
    import_jobs: object | None
    current_user: Callable
    workspace_admin_for: Callable
    record_audit: Callable | None = None


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
        refresh_operational_gauges(
            observability=deps.observability,
            inbox=deps.inbox,
            import_jobs=deps.import_jobs,
            redis_url=deps.redis_url,
        )
        status = 200 if body["ready"] else 503
        return Response(
            content=__import__("json").dumps(body, ensure_ascii=False),
            media_type="application/json",
            status_code=status,
        )

    @app.get("/metrics")
    def metrics():
        refresh_operational_gauges(
            observability=deps.observability,
            inbox=deps.inbox,
            import_jobs=deps.import_jobs,
            redis_url=deps.redis_url,
        )
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

    def _require_debug_admin(authorization: str | None, x_tenant_id: str | None) -> tuple[dict, str]:
        user = deps.current_user(authorization)
        if not x_tenant_id:
            raise DomainError("VALIDATION_ERROR", "X-Tenant-Id required")
        if not deps.workspace_admin_for(user, x_tenant_id):
            raise DomainError("FORBIDDEN_WORKSPACE", "admin required")
        return user, x_tenant_id

    def _audit_debug_access(
        *,
        user: dict,
        tenant_id: str,
        request_id: str,
        action: str,
    ) -> None:
        if deps.record_audit is None:
            return
        deps.record_audit(
            tenant_id=TenantId(tenant_id),
            actor_user_id=UserId(user["user_id"]),
            action=action,
            resource_type="decision_trace",
            resource_id=request_id,
            persona_id=None,
            payload={"request_id": request_id},
        )

    @app.get("/v1/debug/requests/{request_id}")
    def get_debug_request(
        request_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user, tenant_id = _require_debug_admin(authorization, x_tenant_id)
        if deps.decision_traces is None:
            raise DomainError("NOT_FOUND", "trace not found")
        entry = deps.decision_traces.get_by_request_id(tenant_id, request_id)
        if entry is None:
            raise DomainError("NOT_FOUND", "trace not found")
        _audit_debug_access(
            user=user,
            tenant_id=tenant_id,
            request_id=request_id,
            action="observability.debug_view",
        )
        return {
            "request_id": entry["request_id"],
            "tenant_id": entry["tenant_id"],
            "persona_id": entry.get("persona_id"),
            "thread_id": entry.get("thread_id"),
            "message_id": entry.get("message_id"),
            "created_at": entry.get("created_at"),
            "expires_at": entry.get("expires_at"),
            "content_sampled": bool(entry.get("content_sampled")),
            "decision_trace": entry.get("summary_json") or {},
        }

    @app.get("/v1/debug/requests/{request_id}/content")
    def get_debug_request_content(
        request_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user, tenant_id = _require_debug_admin(authorization, x_tenant_id)
        if deps.decision_traces is None:
            raise DomainError("NOT_FOUND", "trace not found")
        entry = deps.decision_traces.get_by_request_id(tenant_id, request_id)
        if entry is None:
            raise DomainError("NOT_FOUND", "trace not found")
        if not entry.get("content_sampled") or not entry.get("encrypted_payload"):
            raise DomainError("NOT_FOUND", "content not sampled")
        decrypted = decrypt_payload(str(entry["encrypted_payload"]))
        if decrypted is None:
            raise DomainError("UPSTREAM_UNAVAILABLE", "content unavailable")
        _audit_debug_access(
            user=user,
            tenant_id=tenant_id,
            request_id=request_id,
            action="observability.debug_content",
        )
        return {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "content": decrypted,
        }

    @app.delete("/v1/debug/requests/{request_id}", status_code=204)
    def delete_debug_request(
        request_id: str,
        authorization: str | None = Header(default=None),
        x_tenant_id: str | None = Header(default=None),
    ):
        user, tenant_id = _require_debug_admin(authorization, x_tenant_id)
        if deps.decision_traces is None or not hasattr(deps.decision_traces, "delete_by_request_id"):
            raise DomainError("NOT_FOUND", "trace not found")
        deleted = deps.decision_traces.delete_by_request_id(tenant_id, request_id)
        if not deleted:
            raise DomainError("NOT_FOUND", "trace not found")
        _audit_debug_access(
            user=user,
            tenant_id=tenant_id,
            request_id=request_id,
            action="observability.debug_delete",
        )
        return Response(status_code=204)
