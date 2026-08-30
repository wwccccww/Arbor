from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

from arbor.observability.context import current_request_context, tenant_id_hash

_REDACTED_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "prompt",
        "user_message",
        "model_response",
        "reasoning_content",
        "password",
        "token",
        "cookie",
    }
)


def _sanitize_log_field(key: str, value: object) -> object:
    lowered = key.lower()
    if lowered in _REDACTED_KEYS or lowered.endswith(("_token", "_key")):
        return "[REDACTED]"
    if lowered in {"content", "text", "body"} and isinstance(value, str) and len(value) > 256:
        return f"[REDACTED len={len(value)}]"
    return value


class JsonEventLogger:
    def __init__(self, *, service: str, logger: logging.Logger | None = None) -> None:
        self.service = service
        self.logger = logger or logging.getLogger("arbor.observability")

    def emit(self, event: str, level: str = "INFO", **fields: object) -> None:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": level,
            "service": self.service,
            "event": event,
        }
        ctx = current_request_context()
        if ctx is not None:
            payload["request_id"] = ctx.request_id
            if ctx.trace_id:
                payload["trace_id"] = ctx.trace_id
            if ctx.tenant_id:
                payload["tenant_id_hash"] = tenant_id_hash(ctx.tenant_id)
            if ctx.persona_id:
                payload["persona_id"] = ctx.persona_id
            if ctx.thread_id:
                payload["thread_id"] = ctx.thread_id
            if ctx.actor_id:
                payload["actor_id"] = ctx.actor_id
        for key, value in fields.items():
            if value is not None:
                payload[key] = _sanitize_log_field(key, value)
        level_no = logging.INFO
        if level.upper() == "WARNING":
            level_no = logging.WARNING
        elif level.upper() == "ERROR":
            level_no = logging.ERROR
        elif level.upper() == "DEBUG":
            level_no = logging.DEBUG
        self.logger.log(
            level_no,
            json.dumps(payload, ensure_ascii=False, default=str),
        )


def text_hash(text: str) -> str:
    digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
