"""Execute agent run advancement (ARQ worker or sync queue)."""

from __future__ import annotations

import logging

from arbor.adapters.outbound.arq.agent_runtime import build_agent_runtime
from arbor.adapters.outbound.tools.stub_ticket import StubTicketTool
from arbor.domain.shared.ids import TenantId, UserId
from arbor.env import database_url as env_database_url
from arbor.observability.context import RequestContext, reset_request_context, set_request_context
from arbor.observability.runtime import build_observability

logger = logging.getLogger("arbor.worker")


def execute_agent_run(payload: dict) -> None:
    request_id = str(payload.get("request_id") or payload.get("run_id") or "")
    tenant_id = str(payload.get("tenant_id") or "")
    run_id = str(payload.get("run_id") or "")
    user_id = str(payload.get("user_id") or "")
    expected_version = payload.get("expected_version")
    token = set_request_context(
        RequestContext(
            request_id=request_id or "worker-agent",
            tenant_id=tenant_id or None,
        )
    )
    observability = build_observability(service="arbor-worker")
    url = env_database_url() or None
    if url:
        from arbor.adapters.outbound.postgres.connection import reachable

        if not reachable(url):
            logger.warning("DATABASE_URL unreachable; worker using in-memory store")
            url = None
    try:
        runtime = build_agent_runtime(
            database_url=url,
            observability=observability,
            ticket_tool=StubTicketTool(),
        )
        guard = 0
        while guard < 16:
            guard += 1
            run = runtime.advance_run(
                tenant_id=TenantId(tenant_id),
                user_id=UserId(user_id),
                run_id=run_id,
                expected_version=int(expected_version) if expected_version is not None else None,
                enqueue_next=False,
            )
            if run.is_terminal() or run.status.value == "waiting_approval":
                if run.status.value == "completed" and run.final_output:
                    runtime.extract_memory(
                        tenant_id=TenantId(tenant_id),
                        user_id=UserId(user_id),
                        persona_id=run.persona_id,
                        run_id=run.id,
                        goal=run.goal,
                        final_output=run.final_output,
                        tool_results=list(run.metadata.get("tool_results") or []),
                    )
                break
            expected_version = run.version
    finally:
        reset_request_context(token)
