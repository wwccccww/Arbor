"""Execute a single import job (ARQ worker or sync queue)."""

from __future__ import annotations

import logging

from arbor.adapters.outbound.arq.import_runtime import build_import_job_runtime
from arbor.adapters.outbound.deepseek import DeepSeekReasoner
from arbor.env import chat_api_key
from arbor.env import database_url as env_database_url
from arbor.observability.context import RequestContext, reset_request_context, set_request_context
from arbor.observability.runtime import build_observability

logger = logging.getLogger("arbor.worker")


def execute_import_job(payload: dict) -> None:
    request_id = str(payload.get("request_id") or payload.get("job_id") or "")
    token = set_request_context(
        RequestContext(
            request_id=request_id or "worker-import",
            tenant_id=str(payload.get("tenant_id") or "") or None,
        )
    )
    observability = build_observability(service="arbor-worker")
    reasoner = DeepSeekReasoner(observability=observability) if chat_api_key() else None
    url = env_database_url() or None
    if url:
        from arbor.adapters.outbound.postgres.connection import reachable

        if not reachable(url):
            logger.warning("DATABASE_URL unreachable; worker using in-memory store")
            url = None
    try:
        runtime = build_import_job_runtime(
            database_url=url,
            reasoner=reasoner,
            observability=observability,
        )
        runtime.run_import(payload)
    finally:
        reset_request_context(token)
