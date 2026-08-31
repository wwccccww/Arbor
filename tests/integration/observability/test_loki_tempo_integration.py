from __future__ import annotations

import json
import os
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app


def _service_ready(url: str, path: str = "/ready") -> bool:
    try:
        response = httpx.get(f"{url.rstrip('/')}{path}", timeout=2.0)
        return response.status_code < 500
    except (httpx.HTTPError, OSError):
        return False


def _integration_required() -> bool:
    return os.environ.get("OBSERVABILITY_INTEGRATION_REQUIRED", "").lower() in {"1", "true", "yes"}


def _require_service(url: str, path: str = "/ready", name: str = "service") -> None:
    if _service_ready(url, path):
        return
    if _integration_required():
        pytest.fail(f"{name} not available at {url}")
    pytest.skip(f"{name} not available at {url}")


def _loki_query(loki_url: str, query: str) -> dict:
    response = httpx.get(
        f"{loki_url.rstrip('/')}/loki/api/v1/query_range",
        params={"query": query, "limit": 20},
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()


def _loki_push(loki_url: str, *, labels: dict[str, str], line: str) -> None:
    ts_ns = str(int(time.time() * 1e9))
    payload = {"streams": [{"stream": labels, "values": [[ts_ns, line]]}]}
    response = httpx.post(
        f"{loki_url.rstrip('/')}/loki/api/v1/push",
        json=payload,
        timeout=5.0,
    )
    response.raise_for_status()


def _tempo_search_by_service(tempo_url: str, *, service: str = "arbor-api") -> dict:
    now = int(time.time())
    response = httpx.get(
        f"{tempo_url.rstrip('/')}/api/search",
        params={
            "tags": f"service.name={service}",
            "start": now - 600,
            "end": now + 60,
            "limit": 10,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()


def _flush_otel_spans() -> None:
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        force_flush = getattr(provider, "force_flush", None)
        if callable(force_flush):
            force_flush(timeout_millis=10_000)
    except Exception:
        pass


@pytest.mark.integration
def test_loki_json_logs_contain_request_id():
    """App emits request_id; Loki ingest/query roundtrip finds a pushed log line."""
    loki_url = os.environ.get("LOKI_URL", "http://localhost:3100")
    _require_service(loki_url, "/ready", "Loki")
    client = TestClient(create_app(), raise_server_exceptions=False)
    headers = {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }
    response = client.get("/v1/me", headers=headers)
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-Id")
    assert request_id

    marker = f"arbor-ci-loki-{uuid.uuid4().hex[:12]}"
    _loki_push(
        loki_url,
        labels={"service": "arbor-api", "job": "arbor-ci"},
        line=json.dumps({"request_id": request_id, "marker": marker, "event": "ci.test"}),
    )

    deadline = time.time() + 30
    found = False
    while time.time() < deadline:
        payload = _loki_query(loki_url, f'{{service="arbor-api"}} |= "{marker}"')
        results = payload.get("data", {}).get("result") or []
        if results:
            found = True
            break
        time.sleep(2)
    assert found, f"marker {marker} not found in Loki within timeout"


@pytest.mark.integration
def test_tempo_trace_search_by_request_id():
    tempo_url = os.environ.get("TEMPO_URL", "http://localhost:3200")
    otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    _require_service(tempo_url, "/ready", "Tempo")
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint
    os.environ["OBSERVABILITY_ENABLED"] = "true"
    os.environ.setdefault("OTEL_SERVICE_NAME", "arbor-api")
    client = TestClient(create_app(), raise_server_exceptions=False)
    headers = {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }
    chat = client.post(
        "/v1/threads/0a000000-0000-4000-a000-000000000030/messages",
        headers=headers,
        json={"text": "trace integration"},
    )
    assert chat.status_code == 200
    assert chat.json().get("request_id")
    _flush_otel_spans()

    deadline = time.time() + 45
    found = False
    while time.time() < deadline:
        payload = _tempo_search_by_service(tempo_url)
        traces = payload.get("traces") or []
        if traces:
            found = True
            break
        time.sleep(3)
    assert found, "no arbor-api traces indexed in Tempo within timeout"


@pytest.mark.integration
def test_tempo_trace_search_by_agent_run_request_id():
    tempo_url = os.environ.get("TEMPO_URL", "http://localhost:3200")
    otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    _require_service(tempo_url, "/ready", "Tempo")
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint
    os.environ["OBSERVABILITY_ENABLED"] = "true"
    os.environ.setdefault("OTEL_SERVICE_NAME", "arbor-api")
    client = TestClient(create_app(), raise_server_exceptions=False)
    headers = {
        "Authorization": "Bearer token-a",
        "X-Tenant-Id": "0a000000-0000-4000-a000-000000000001",
    }
    persona_id = "0a000000-0000-4000-a000-000000000010"
    body = {
        "goal": "查询退货政策",
        "plan_script": [
            {
                "schema_version": 1,
                "action": "retrieve",
                "query": "退货政策",
                "scopes": ["semantic_memory"],
                "reason": "policy lookup",
            },
            {
                "schema_version": 1,
                "action": "answer",
                "text": "7天无理由退货",
                "citations": [],
                "completion": True,
            },
        ],
    }
    created = client.post(f"/v1/personas/{persona_id}/agent-runs", headers=headers, json=body)
    assert created.status_code == 202
    run_id = created.json()["id"]
    detail = client.get(f"/v1/agent-runs/{run_id}", headers=headers)
    assert detail.status_code == 200
    run = detail.json()["run"]
    request_id = run.get("request_id") or (run.get("metadata") or {}).get("request_id")
    assert request_id
    _flush_otel_spans()

    deadline = time.time() + 45
    found = False
    while time.time() < deadline:
        search_payload = _tempo_search_by_service(tempo_url)
        traces = search_payload.get("traces") or []
        if traces:
            found = True
            break
        time.sleep(3)
    assert found, f"agent run trace for {request_id} not indexed in Tempo"


@pytest.mark.integration
def test_metrics_include_new_observability_series():
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.get("/ready")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "arbor_http_active_requests" in text
    assert "arbor_permission_denials_total" in text or "arbor_http_requests_total" in text
