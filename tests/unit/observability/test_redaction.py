from __future__ import annotations

import json
import logging

from arbor.observability.context import RequestContext, reset_request_context, set_request_context
from arbor.observability.json_log import JsonEventLogger


def test_json_log_redacts_authorization_and_bearer(caplog):
    logger = JsonEventLogger(service="arbor-test")
    token = set_request_context(RequestContext(request_id="01JTESTREQUESTID0000000001"))
    caplog.set_level(logging.INFO, logger="arbor.observability")
    try:
        logger.emit(
            "llm.chat",
            authorization="Bearer secret-token",
            prompt="用户说了敏感内容",
            api_key="sk-test",
            model="scripted",
        )
    finally:
        reset_request_context(token)

    assert caplog.records
    output = caplog.records[-1].message
    assert "secret-token" not in output
    payload = json.loads(output)
    assert payload["authorization"] == "[REDACTED]"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["prompt"] == "[REDACTED]"
    assert payload["model"] == "scripted"
