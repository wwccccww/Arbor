from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryObjectStorage,
    InMemoryPersonaRepository,
    SeqIdGenerator,
)
from arbor.application.memory.commands import ImportArtifact
from arbor.adapters.outbound.multimodal.factory import parse_media_bytes
from arbor.application.memory.media_to_inbox import MediaToInbox
from arbor.application.memory.process_import import ProcessImportJob
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack, test_import_requires_write_memory


def test_import_artifact():
    test_import_requires_write_memory()


def test_process_import_writes_inbox_not_memory():
    stores, _send = _stack()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    memories = InMemoryMemoryRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    before = {item.id for item in memories.list_active(tenant, persona)}
    ImportArtifact(
        personas=InMemoryPersonaRepository(stores),
        storage=InMemoryObjectStorage(stores),
        auth=AuthorizationPolicy(),
    )(
        tenant_id=tenant,
        user_id=USER,
        persona_id=persona,
        filename="notes.txt",
        data="导入待确认abc".encode(),
        capabilities=list(Capability),
    )
    media = MediaToInbox(
        personas=InMemoryPersonaRepository(stores),
        inbox=inbox,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        parse_media=parse_media_bytes,
    )
    result = ProcessImportJob(media_to_inbox=media)(
        tenant_id=tenant,
        user_id=USER,
        persona_id=persona,
        filename="notes.txt",
        data="导入待确认abc".encode(),
        capabilities=list(Capability),
    )
    assert result.inbox_created == 1
    pending = inbox.list_pending(tenant, persona)
    assert [item.payload["text"] for item in pending] == ["导入待确认abc"]
    after = {item.id for item in memories.list_active(tenant, persona)}
    assert after == before
