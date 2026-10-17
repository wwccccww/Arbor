"""A worker crash must never leave an import job pending forever."""

from __future__ import annotations

import os

import pytest

from arbor.adapters.outbound.postgres.import_jobs import PgImportJobRepository
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT = "0a000000-0000-4000-a000-000000000001"
PERSONA = "0a000000-0000-4000-a000-000000000010"
USER = "0a000000-0000-4000-a000-000000000002"
JOB = "d0000000-0000-4000-a000-000000000001"
OBJECT_URI = f"imports/{TENANT}/{PERSONA}/{JOB}/sample.txt"


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_worker_records_failure_when_the_runtime_never_runs(pg) -> None:
    from arbor.adapters.outbound.arq.runner import execute_import_job

    jobs = PgImportJobRepository(pg.conn)
    jobs.save(
        {
            "id": JOB,
            "tenant_id": TENANT,
            "persona_id": PERSONA,
            "filename": "sample.txt",
            "object_uri": OBJECT_URI,
            "hint": None,
            "status": "pending",
            "inbox_created": 0,
            "error": None,
        }
    )
    assert jobs.get(TENANT, JOB)["status"] == "pending"

    payload = {
        "job_id": JOB,
        "tenant_id": TENANT,
        "object_uri": OBJECT_URI,
        "filename": "sample.txt",
        "user_id": USER,
        "request_id": "contract-import-failure",
    }

    # persona_id is deliberately absent: RunImportJob raises on it before its own
    # error handling runs, which is the crash shape the worker has to record.
    with pytest.raises(KeyError):
        execute_import_job(payload)

    stored = jobs.get(TENANT, JOB)
    assert stored is not None
    assert stored["status"] == "failed"
    assert stored["error"]


@pytest.mark.skipif(
    not (database_url() or os.environ.get("DATABASE_URL")),
    reason="Postgres contract tests need DATABASE_URL",
)
def test_non_final_attempt_leaves_the_job_retryable(pg) -> None:
    from arbor.adapters.outbound.arq.runner import execute_import_job

    jobs = PgImportJobRepository(pg.conn)
    jobs.save(
        {
            "id": JOB,
            "tenant_id": TENANT,
            "persona_id": PERSONA,
            "filename": "sample.txt",
            "object_uri": OBJECT_URI,
            "hint": None,
            "status": "pending",
            "inbox_created": 0,
            "error": None,
        }
    )

    payload = {
        "job_id": JOB,
        "tenant_id": TENANT,
        "object_uri": OBJECT_URI,
        "filename": "sample.txt",
        "user_id": USER,
        "request_id": "contract-import-retry",
    }

    with pytest.raises(KeyError):
        execute_import_job(payload, final_attempt=False)

    assert jobs.get(TENANT, JOB)["status"] == "pending"
