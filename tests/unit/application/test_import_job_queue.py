from __future__ import annotations

from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryObjectStorage,
    InMemoryPersonaRepository,
    SeqIdGenerator,
)
from arbor.adapters.outbound.multimodal.factory import parse_media_bytes
from arbor.adapters.outbound.postgres.import_jobs import InMemoryImportJobRepository
from arbor.application.memory.import_jobs import RunImportJob, SubmitImportJob
from arbor.application.memory.media_to_inbox import MediaToInbox
from arbor.application.memory.process_import import ProcessImportJob
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack


def test_submit_and_run_import_job():
    stores, _ = _stack()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    inbox = InMemoryInboxRepository(stores)
    import_jobs = InMemoryImportJobRepository()
    storage = InMemoryObjectStorage(stores)
    personas = InMemoryPersonaRepository(stores)
    ids = SeqIdGenerator()
    submit = SubmitImportJob(
        personas=personas,
        storage=storage,
        import_jobs=import_jobs,
        ids=ids,
        auth=AuthorizationPolicy(),
    )
    process = ProcessImportJob(
        media_to_inbox=MediaToInbox(
            personas=personas,
            inbox=inbox,
            ids=ids,
            auth=AuthorizationPolicy(),
            parse_media=parse_media_bytes,
        ),
    )
    run = RunImportJob(import_jobs=import_jobs, storage=storage, process_import=process)
    job = submit(
        tenant_id=tenant,
        user_id=USER,
        persona_id=persona,
        filename="notes.txt",
        data="异步导入测试".encode(),
        capabilities=list(Capability),
    )
    assert job["status"] == "pending"
    run(
        {
            "job_id": job["id"],
            "tenant_id": tenant.value,
            "persona_id": persona.value,
            "object_uri": job["object_uri"],
            "filename": job["filename"],
            "hint": None,
            "user_id": USER.value,
        }
    )
    saved = import_jobs.get(tenant.value, job["id"])
    assert saved is not None
    assert saved["status"] == "completed"
    assert saved["inbox_created"] == 1
    pending = inbox.list_pending(tenant, persona)
    assert any(item.payload.get("text") == "异步导入测试" for item in pending)
    assert storage.get(job["object_uri"]) is None
