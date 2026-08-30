from __future__ import annotations

from datetime import UTC, datetime


def cleanup_expired_traces(decision_traces: object | None) -> int:
    if decision_traces is None or not hasattr(decision_traces, "delete_expired"):
        return 0
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return int(decision_traces.delete_expired(now))
