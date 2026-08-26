from __future__ import annotations


class PgImportJobRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def save(self, job: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO import_jobs (
                id, tenant_id, persona_id, filename, object_uri, hint,
                status, inbox_created, error, finished_at,
                parser, media_kind, chunks_parsed
            )
            VALUES (
                %s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s THEN now() ELSE NULL END,
                %s, %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                inbox_created = EXCLUDED.inbox_created,
                error = EXCLUDED.error,
                finished_at = EXCLUDED.finished_at,
                parser = EXCLUDED.parser,
                media_kind = EXCLUDED.media_kind,
                chunks_parsed = EXCLUDED.chunks_parsed
            """,
            (
                job["id"],
                job["tenant_id"],
                job["persona_id"],
                job.get("filename") or "",
                job.get("object_uri"),
                job.get("hint"),
                job.get("status") or "pending",
                int(job.get("inbox_created") or 0),
                job.get("error"),
                bool(job.get("finished")),
                job.get("parser"),
                job.get("media_kind"),
                int(job.get("chunks_parsed") or 0),
            ),
        )

    def update(
        self,
        job_id: str,
        tenant_id: str,
        *,
        status: str | None = None,
        inbox_created: int | None = None,
        error: str | None = None,
        finished: bool = False,
        parser: str | None = None,
        media_kind: str | None = None,
        chunks_parsed: int | None = None,
    ) -> None:
        fields: list[str] = []
        values: list = []
        if status is not None:
            fields.append("status = %s")
            values.append(status)
        if inbox_created is not None:
            fields.append("inbox_created = %s")
            values.append(inbox_created)
        if error is not None:
            fields.append("error = %s")
            values.append(error)
        if finished:
            fields.append("finished_at = now()")
        if parser is not None:
            fields.append("parser = %s")
            values.append(parser)
        if media_kind is not None:
            fields.append("media_kind = %s")
            values.append(media_kind)
        if chunks_parsed is not None:
            fields.append("chunks_parsed = %s")
            values.append(chunks_parsed)
        if not fields:
            return
        values.extend([job_id, tenant_id])
        self.conn.execute(
            f"""
            UPDATE import_jobs
            SET {", ".join(fields)}
            WHERE id = %s AND tenant_id = %s::uuid
            """,
            tuple(values),
        )

    def get(self, tenant_id: str, job_id: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT id, tenant_id, persona_id, filename, status, inbox_created, error,
                   parser, media_kind, chunks_parsed
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
            "error": row.get("error"),
            "parser": row.get("parser"),
            "media_kind": row.get("media_kind"),
            "chunks_parsed": int(row.get("chunks_parsed") or 0),
        }


class InMemoryImportJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}

    def save(self, job: dict) -> None:
        self._jobs[job["id"]] = dict(job)

    def update(
        self,
        job_id: str,
        tenant_id: str,
        *,
        status: str | None = None,
        inbox_created: int | None = None,
        error: str | None = None,
        finished: bool = False,
        parser: str | None = None,
        media_kind: str | None = None,
        chunks_parsed: int | None = None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.get("tenant_id") != tenant_id:
            return
        if status is not None:
            job["status"] = status
        if inbox_created is not None:
            job["inbox_created"] = inbox_created
        if error is not None:
            job["error"] = error
        if finished:
            job["finished"] = True
        if parser is not None:
            job["parser"] = parser
        if media_kind is not None:
            job["media_kind"] = media_kind
        if chunks_parsed is not None:
            job["chunks_parsed"] = chunks_parsed

    def get(self, tenant_id: str, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        if job is None or job.get("tenant_id") != tenant_id:
            return None
        return dict(job)
