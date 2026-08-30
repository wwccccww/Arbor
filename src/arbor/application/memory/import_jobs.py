from __future__ import annotations

import time
from collections.abc import Callable

from arbor.application.memory.media_to_inbox import MediaInboxResult
from arbor.application.storage.object_gc import delete_stored_object
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from arbor.domain.shared.media_kinds import media_kind_for_filename
from arbor.observability.helpers import size_bucket
from arbor.observability.noop import NoopObservability
from arbor.ports.outbound import IdGenerator, ObjectStorage, PersonaRepository


class SubmitImportJob:
    """Store upload bytes, create a pending import job record (no parsing yet)."""

    def __init__(
        self,
        *,
        personas: PersonaRepository,
        storage: ObjectStorage,
        import_jobs,
        ids: IdGenerator,
        auth: AuthorizationPolicy,
        audit: Callable | None = None,
        observability: object | None = None,
    ) -> None:
        self.personas = personas
        self.storage = storage
        self.import_jobs = import_jobs
        self.ids = ids
        self.auth = auth
        self.audit = audit
        self.observability = observability

    def _obs(self):
        return self.observability or NoopObservability()

    def __call__(
        self,
        *,
        tenant_id: TenantId,
        user_id: UserId,
        persona_id: PersonaId,
        filename: str,
        data: bytes,
        hint: str | None = None,
        capabilities: list[Capability] | None = None,
        execution_mode: str = "sync",
    ) -> dict:
        persona = self.personas.get(tenant_id, persona_id)
        caps = capabilities or (self.auth.capabilities_for(persona, user_id) if persona else [])
        if Capability.WRITE_MEMORY not in caps:
            raise DomainError("FORBIDDEN_MEMORY_WRITE", "write_memory required")
        job_id = self.ids.new_id()
        safe_name = filename or "upload.bin"
        object_uri = self.storage.put(
            f"imports/{tenant_id.value}/{persona_id.value}/{job_id}/{safe_name}",
            data,
        )
        job = {
            "id": job_id,
            "tenant_id": tenant_id.value,
            "persona_id": persona_id.value,
            "filename": safe_name,
            "object_uri": object_uri,
            "hint": hint,
            "status": "pending",
            "inbox_created": 0,
            "error": None,
        }
        self.import_jobs.save(job)
        media_kind = media_kind_for_filename(safe_name).value
        obs = self._obs()
        obs.event(
            "import.submitted",
            media_kind=media_kind,
            size_bucket=size_bucket(len(data)),
            execution_mode=execution_mode,
        )
        obs.increment("arbor_import_jobs_total", parser="pending", status="pending")
        if self.audit:
            self.audit(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                action="memory.import",
                resource_type="import",
                resource_id=job_id,
                persona_id=persona_id,
                payload={"filename": safe_name, "job_id": job_id},
            )
        return job


class RunImportJob:
    """Worker: read stored bytes, parse into Inbox, finalize job status."""

    def __init__(self, *, import_jobs, storage, process_import, observability: object | None = None) -> None:
        self.import_jobs = import_jobs
        self.storage = storage
        self.process_import = process_import
        self.observability = observability

    def _obs(self):
        return self.observability or NoopObservability()

    def __call__(self, payload: dict) -> None:
        job_id = str(payload["job_id"])
        tenant_id = str(payload["tenant_id"])
        persona_id = str(payload["persona_id"])
        object_uri = str(payload["object_uri"])
        filename = str(payload.get("filename") or "upload.bin")
        hint = payload.get("hint")
        from arbor.domain.shared.ids import UserId

        user_id = UserId(str(payload["user_id"]))

        job = self.import_jobs.get(tenant_id, job_id)
        if job is None:
            return
        if job.get("status") in {"completed", "failed"}:
            return

        self.import_jobs.update(
            job_id,
            tenant_id,
            status="running",
            error=None,
        )
        data = self.storage.get(object_uri) or b""
        started = time.perf_counter()
        parser = "unknown"
        status = "failed"
        chunks_parsed = 0
        obs = self._obs()
        try:
            from arbor.domain.persona.authorization import Capability
            from arbor.domain.shared.ids import PersonaId, TenantId

            result = self.process_import(
                tenant_id=TenantId(tenant_id),
                user_id=user_id,
                persona_id=PersonaId(persona_id),
                filename=filename,
                data=data,
                hint=hint,
                capabilities=list(Capability),
            )
            if isinstance(result, MediaInboxResult):
                inbox_created = result.inbox_created
                parser = result.parser or "unknown"
                media_kind = result.media_kind
                chunks_parsed = result.chunks_parsed
            else:
                inbox_created = int(result)
                parser = "unknown"
                media_kind = None
                chunks_parsed = inbox_created
            self.import_jobs.update(
                job_id,
                tenant_id,
                status="completed",
                inbox_created=inbox_created,
                error=None,
                finished=True,
                parser=parser,
                media_kind=media_kind,
                chunks_parsed=chunks_parsed,
            )
            status = "completed"
        except Exception as exc:
            self.import_jobs.update(
                job_id,
                tenant_id,
                status="failed",
                error=str(exc),
                finished=True,
            )
            status = "failed"
        finally:
            duration = time.perf_counter() - started
            obs.event(
                "import.process",
                parser=parser,
                chunk_count=chunks_parsed if status == "completed" else 0,
                result=status,
                duration_ms=round(duration * 1000, 2),
            )
            obs.increment("arbor_import_jobs_total", parser=parser, status=status)
            obs.observe("arbor_import_job_duration_seconds", duration, parser=parser, status=status)
            delete_stored_object(self.storage, object_uri)
