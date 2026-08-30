from __future__ import annotations

from datetime import UTC, datetime, timedelta

from arbor.adapters.outbound.inmemory import InMemoryDecisionTraceRepository, InMemoryStores
from arbor.observability.cleanup import cleanup_expired_traces


def test_cleanup_expired_traces():
    stores = InMemoryStores()
    repo = InMemoryDecisionTraceRepository(stores)
    expired = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    repo.save({"request_id": "old", "tenant_id": "t1", "expires_at": expired})
    repo.save({"request_id": "new", "tenant_id": "t1", "expires_at": future})
    deleted = cleanup_expired_traces(repo)
    assert deleted == 1
    assert repo.get_by_request_id("t1", "old") is None
    assert repo.get_by_request_id("t1", "new") is not None
