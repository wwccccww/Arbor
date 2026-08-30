from __future__ import annotations

from arbor.domain.shared.ids import TenantId
from arbor.observability.helpers import obs_or_noop


def refresh_operational_gauges(
    *,
    observability: object | None,
    inbox: object | None,
    import_jobs: object | None,
    tenant_ids: list[str] | None = None,
) -> None:
    obs = obs_or_noop(observability)
    pending_total = 0
    if inbox is not None and hasattr(inbox, "count_pending"):
        pending_total = int(inbox.count_pending())
    elif inbox is not None and tenant_ids:
        for tid in tenant_ids:
            if hasattr(inbox, "list_pending_for_tenant"):
                pending_total += len(inbox.list_pending_for_tenant(tid))
    obs.set_gauge("arbor_inbox_pending", float(pending_total))

    in_progress = 0
    if import_jobs is not None and hasattr(import_jobs, "count_by_status"):
        in_progress = int(import_jobs.count_by_status("running"))
    obs.set_gauge("arbor_import_jobs_in_progress", float(in_progress))


def inbox_pending_count(inbox: object, tenant_id: TenantId) -> int:
    if hasattr(inbox, "count_pending"):
        return int(inbox.count_pending(tenant_id))
    pending = inbox.list_pending(tenant_id, None) if hasattr(inbox, "list_pending") else []
    return len(pending)
