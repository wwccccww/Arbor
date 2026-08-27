from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    ScriptedReasoner,
    SeqIdGenerator,
)
from arbor.adapters.outbound.multimodal.factory import parse_media_bytes
from arbor.application.memory.media_to_inbox import MediaToInbox
from arbor.application.memory.process_import import ProcessImportJob
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def test_process_import_chunks_long_chat_export():
    stores = InMemoryStores()
    personas = InMemoryPersonaRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona_id = PersonaId("0a000000-0000-4000-a000-000000000010")
    media = MediaToInbox(
        personas=personas,
        inbox=inbox,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        reasoner=ScriptedReasoner(),
        parse_media=parse_media_bytes,
    )
    process = ProcessImportJob(media_to_inbox=media)
    chat = (
        "2024-11-02 我：今晚去面馆？\n"
        "2024-11-02 林夏：别放香菜。\n"
        "2024-11-02 我们在店里吵起来了。"
    )
    result = process(
        tenant_id=tenant,
        user_id=UserId("0a000000-0000-4000-a000-000000000002"),
        persona_id=persona_id,
        filename="chat.txt",
        data=chat.encode(),
        capabilities=list(Capability),
    )
    assert result.inbox_created == 1
    assert result.parser == "plain_text"
    pending = inbox.list_pending(tenant, persona_id)
    assert len(pending) == 1
    assert "吵" in pending[0].payload.get("text", "")


def test_process_import_uses_reasoner_extraction_on_short_blob():
    stores = InMemoryStores()
    personas = InMemoryPersonaRepository(stores)
    inbox = InMemoryInboxRepository(stores)
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona_id = PersonaId("0a000000-0000-4000-a000-000000000010")
    media = MediaToInbox(
        personas=personas,
        inbox=inbox,
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
        reasoner=ScriptedReasoner(proposed_fact="林夏讨厌香菜"),
        parse_media=parse_media_bytes,
    )
    process = ProcessImportJob(media_to_inbox=media)
    result = process(
        tenant_id=tenant,
        user_id=UserId("0a000000-0000-4000-a000-000000000002"),
        persona_id=persona_id,
        filename="notes.txt",
        data="她从来不吃香菜".encode(),
        capabilities=list(Capability),
    )
    assert result.inbox_created == 1
    pending = inbox.list_pending(tenant, persona_id)
    assert pending[0].payload["text"] == "林夏讨厌香菜"
