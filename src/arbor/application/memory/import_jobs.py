from __future__ import annotations

from typing import Callable

from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
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
    ) -> None:
        self.personas = personas
        self.storage = storage
        self.import_jobs = import_jobs
        self.ids = ids
        self.auth = auth
        self.audit = audit

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

    def __init__(self, *, import_jobs, storage: ObjectStorage, process_import) -> None:
        self.import_jobs = import_jobs
        self.storage = storage
        self.process_import = process_import

    def __call__(self, payload: dict) -> None:
        job_id = str(payload["job_id"])
        tenant_id = str(payload["tenant_id"])
        persona_id = str(payload["persona_id"])
        object_uri = str(payload["object_uri"])
        filename = str(payload.get("filename") or "upload.bin")
        hint = payload.get("hint")
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
        try:
            inbox_created = self.process_import(
                tenant_id=TenantId(tenant_id),
                user_id=user_id,
                persona_id=PersonaId(persona_id),
                filename=filename,
                data=data,
                hint=hint,
                capabilities=list(Capability),
            )
            self.import_jobs.update(
                job_id,
                tenant_id,
                status="completed",
                inbox_created=inbox_created,
                error=None,
                finished=True,
            )
        except Exception as exc:
            self.import_jobs.update(
                job_id,
                tenant_id,
                status="failed",
                error=str(exc),
                finished=True,
            )
