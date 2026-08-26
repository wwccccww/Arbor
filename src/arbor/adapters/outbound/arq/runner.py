"""Execute a single import job (ARQ worker or sync queue)."""

from __future__ import annotations

import logging

from arbor.adapters.outbound.arq.import_runtime import build_import_job_runtime
from arbor.adapters.outbound.deepseek import DeepSeekReasoner
from arbor.env import chat_api_key
from arbor.env import database_url as env_database_url

logger = logging.getLogger("arbor.worker")


def execute_import_job(payload: dict) -> None:
    reasoner = DeepSeekReasoner() if chat_api_key() else None
    url = env_database_url() or None
    if url:
        from arbor.adapters.outbound.postgres.connection import reachable

        if not reachable(url):
            logger.warning("DATABASE_URL unreachable; worker using in-memory store")
            url = None
    runtime = build_import_job_runtime(database_url=url, reasoner=reasoner)
    runtime.run_import(payload)
