from __future__ import annotations

import threading
import time
from collections.abc import Callable

from fastapi import Request, Response

from arbor.observability.context import (
    RequestContext,
    merge_request_context,
    normalize_request_id,
    reset_request_context,
    set_request_context,
)


def _status_class(status_code: int) -> str:
    if status_code < 200:
        return "1xx"
    if status_code < 300:
        return "2xx"
    if status_code < 400:
        return "3xx"
    if status_code < 500:
        return "4xx"
    return "5xx"


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    return request.url.path


def register_observability_middleware(app, observability) -> None:
    lock = threading.Lock()
    active_count = {"n": 0}

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next: Callable) -> Response:
        with lock:
            active_count["n"] += 1
            observability.set_gauge("arbor_http_active_requests", float(active_count["n"]))
        incoming = normalize_request_id(request.headers.get("X-Request-Id"))
        trace_id = request.headers.get("traceparent")
        tenant_header = request.headers.get("x-tenant-id")
        ctx = RequestContext(
            request_id=incoming,
            trace_id=trace_id,
            tenant_id=tenant_header,
        )
        token = set_request_context(ctx)
        started = time.perf_counter()
        route = _route_template(request)
        method = request.method.upper()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = incoming
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - started
            status_class = _status_class(status_code)
            observability.increment(
                "arbor_http_requests_total",
                route=route,
                method=method,
                status_class=status_class,
            )
            observability.observe(
                "arbor_http_request_duration_seconds",
                duration,
                route=route,
                method=method,
            )
            observability.event(
                "http.request",
                route=route,
                method=method,
                status_class=status_class,
                duration_ms=round(duration * 1000, 2),
                result="success" if status_code < 500 else "error",
            )
            with lock:
                active_count["n"] = max(0, active_count["n"] - 1)
                observability.set_gauge("arbor_http_active_requests", float(active_count["n"]))
            reset_request_context(token)


def bind_request_context(**updates: object) -> object:
    merged = merge_request_context(**updates)
    return set_request_context(merged)
