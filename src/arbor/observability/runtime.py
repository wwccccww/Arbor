from __future__ import annotations

import logging
import os
from typing import Any

from arbor.env import chat_api_key, database_url, embedding_api_key, job_queue_backend, redis_url
from arbor.observability.json_log import JsonEventLogger
from arbor.observability.metrics import build_prometheus_registry
from arbor.observability.noop import NoopObservability
from arbor.observability.port import ObservabilityPort
from arbor.observability.production import ProductionObservability


def observability_enabled() -> bool:
    raw = (os.environ.get("OBSERVABILITY_ENABLED") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def log_format() -> str:
    return (os.environ.get("LOG_FORMAT") or "json").strip().lower()


def decision_trace_retention_days() -> int:
    raw = (os.environ.get("DECISION_TRACE_RETENTION_DAYS") or "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def otel_service_name() -> str:
    return (os.environ.get("OTEL_SERVICE_NAME") or "arbor-api").strip() or "arbor-api"


def otel_exporter_endpoint() -> str:
    return (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip()


def build_observability(service: str = "arbor-api") -> ObservabilityPort:
    if not observability_enabled():
        return NoopObservability()
    logger = JsonEventLogger(service=service)
    if log_format() != "json":
        logging.getLogger("arbor.observability").warning(
            "LOG_FORMAT=%s ignored; JSON logs always emitted",
            log_format(),
        )
    metrics = build_prometheus_registry()
    tracer = _build_tracer(service)
    return ProductionObservability(logger=logger, metrics=metrics, tracer=tracer)


def _build_tracer(service: str) -> Any | None:
    endpoint = otel_exporter_endpoint()
    if not endpoint:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return trace.get_tracer("arbor")
    except ImportError:
        logging.getLogger("arbor.observability").warning("OpenTelemetry packages missing; trace export disabled")
        return None


def check_readiness(
    *,
    database_url_configured: str | None,
    redis_url_configured: str | None,
    object_store_backend: str,
    postgres_reachable: bool | None = None,
    redis_reachable: bool | None = None,
) -> dict:
    checks: dict[str, dict[str, object]] = {}
    if database_url_configured:
        checks["postgres"] = {
            "required": True,
            "ok": bool(postgres_reachable),
        }
    else:
        checks["postgres"] = {"required": False, "ok": True}

    queue_backend = job_queue_backend()
    if queue_backend == "redis":
        checks["redis"] = {
            "required": True,
            "ok": bool(redis_reachable if redis_url_configured else False),
        }
    else:
        checks["redis"] = {"required": False, "ok": True}

    checks["object_store"] = {
        "required": object_store_backend != "local",
        "ok": True,
        "backend": object_store_backend,
    }
    checks["llm"] = {
        "required": bool(chat_api_key()),
        "configured": bool(chat_api_key()),
        "ok": True,
    }
    checks["embedding"] = {
        "required": bool(embedding_api_key()),
        "configured": bool(embedding_api_key()),
        "ok": True,
    }
    ready = all(bool(item.get("ok")) for item in checks.values() if item.get("required"))
    return {"ready": ready, "checks": checks}


def probe_dependencies(session: object | None) -> dict[str, bool | None]:
    postgres_ok: bool | None = None
    redis_ok: bool | None = None
    url = database_url()
    if url:
        try:
            from arbor.adapters.outbound.postgres.connection import reachable

            postgres_ok = reachable(url)
        except OSError:
            postgres_ok = False
    redis = redis_url()
    if redis and job_queue_backend() == "redis":
        try:
            import redis as redis_lib

            client = redis_lib.from_url(redis)
            redis_ok = bool(client.ping())
        except (OSError, ImportError):
            redis_ok = False
    return {"postgres": postgres_ok, "redis": redis_ok}
