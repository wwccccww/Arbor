from __future__ import annotations

import re

_FORBIDDEN_LABEL_KEYS = frozenset(
    {
        "request_id",
        "tenant_id",
        "persona_id",
        "thread_id",
        "message_id",
        "job_id",
        "user_id",
        "actor_id",
    }
)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    flags=re.IGNORECASE,
)
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def sanitize_label_value(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "unknown"
    if _UUID_RE.fullmatch(text) or _ULID_RE.fullmatch(text):
        raise ValueError("high-cardinality label value")
    if len(text) > 64:
        return text[:64]
    return text


def validate_metric_labels(labels: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, raw in labels.items():
        if key in _FORBIDDEN_LABEL_KEYS:
            raise ValueError(f"forbidden metric label: {key}")
        out[key] = sanitize_label_value(str(raw))
    return out
