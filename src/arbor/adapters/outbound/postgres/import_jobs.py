from __future__ import annotations


class PgImportJobRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def save(self, job: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO import_jobs (
                id, tenant_id, persona_id, filename, object_uri, hint,
                status, inbox_created, error, finished_at
            )
            VALUES (
                %s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, now()
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                inbox_created = EXCLUDED.inbox_created,
                error = EXCLUDED.error,
                finished_at = EXCLUDED.finished_at
            """,
            (
                job["id"],
                job["tenant_id"],
                job["persona_id"],
                job.get("filename") or "",
                job.get("object_uri"),
                job.get("hint"),
                job.get("status") or "completed",
                int(job.get("inbox_created") or 0),
                job.get("error"),
            ),
        )

    def get(self, tenant_id: str, job_id: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, filename, status, inbox_created
            FROM import_jobs
            WHERE id = %s AND tenant_id = %s::uuid
            """,
            (job_id, tenant_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "persona_id": str(row["persona_id"]),
            "filename": str(row["filename"] or ""),
            "status": str(row["status"] or ""),
            "inbox_created": int(row["inbox_created"] or 0),
        }


class InMemoryImportJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}

    def save(self, job: dict) -> None:
        self._jobs[job["id"]] = dict(job)

    def get(self, tenant_id: str, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        if job is None or job.get("tenant_id") != tenant_id:
            return None
        return dict(job)
