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


def record_import_job_failure(payload: dict, exc: Exception) -> None:
    """Best-effort terminal status for a job that died before RunImportJob ran.

    RunImportJob marks its own failures, but it is only reached once the runtime
    is built. A crash during assembly would otherwise leave the record at
    `pending` forever and the workbench would poll it indefinitely.
    """
    job_id = str(payload.get("job_id") or "")
    tenant_id = str(payload.get("tenant_id") or "")
    url = env_database_url() or None
    if not job_id or not tenant_id or not url:
        return
    try:
        from arbor.adapters.outbound.postgres import PostgresSession
        from arbor.adapters.outbound.postgres.import_jobs import PgImportJobRepository

        session = PostgresSession.connect(url)
        try:
            jobs = PgImportJobRepository(session.conn)
            job = jobs.get(tenant_id, job_id)
            if job is not None and job.get("status") not in {"completed", "failed"}:
                jobs.update(job_id, tenant_id, status="failed", error=str(exc), finished=True)
        finally:
            session.close()
    except Exception:
        logger.exception("could not record failure for import job %s", job_id)


def execute_import_job(payload: dict, *, final_attempt: bool = True) -> None:
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
    except Exception as exc:
        logger.exception("import job %s failed", payload.get("job_id"))
        if final_attempt:
            record_import_job_failure(payload, exc)
        raise
    finally:
        reset_request_context(token)
