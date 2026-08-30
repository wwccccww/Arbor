from __future__ import annotations

import pytest

from arbor.observability.labels import sanitize_label_value, validate_metric_labels


def test_validate_metric_labels_rejects_request_id_key():
    with pytest.raises(ValueError, match="forbidden"):
        validate_metric_labels({"request_id": "01JABCDEFGHJKMNPQRSTVWXYZ0"})


def test_sanitize_label_value_rejects_uuid():
    with pytest.raises(ValueError, match="high-cardinality"):
        sanitize_label_value("0a000000-0000-4000-a000-000000000001")


def test_validate_metric_labels_accepts_route():
    labels = validate_metric_labels({"route": "/v1/me", "method": "GET", "status_class": "2xx"})
    assert labels["route"] == "/v1/me"
