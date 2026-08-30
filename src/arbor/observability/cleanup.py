from __future__ import annotations

from datetime import UTC, datetime

from arbor.observability.content_storage import delete_encrypted_content


def cleanup_expired_traces(decision_traces: object | None, storage: object | None = None) -> int:
    if decision_traces is None or not hasattr(decision_traces, "delete_expired"):
        return 0
    now = datetime.now(UTC).isoformat()
    removed = decision_traces.delete_expired(now)
    if isinstance(removed, int):
        return removed
    for entry in removed or []:
        delete_encrypted_content(entry, storage)
    return len(removed or [])
