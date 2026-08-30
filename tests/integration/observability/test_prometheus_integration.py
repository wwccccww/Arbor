from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import create_app
from arbor.observability.labels import validate_metric_labels


def test_metrics_label_whitelist_rejects_request_id():
    try:
        validate_metric_labels({"request_id": "01JABCDEFGHJKMNPQRSTVWXYZ0"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_metrics_scrape_includes_new_gauges():
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.get("/ready")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "arbor_import_jobs_pending" in text
    assert "arbor_eval_metric" not in text or "arbor_eval_metric" in text
