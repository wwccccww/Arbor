from __future__ import annotations

from datetime import UTC, datetime


def inbox_age_seconds(created_at: str | None) -> float | None:
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return round((datetime.now(UTC) - created).total_seconds(), 1)
    except (TypeError, ValueError):
        return None
