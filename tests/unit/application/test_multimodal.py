from arbor.adapters.outbound.multimodal.document_parser import parse_document
from arbor.adapters.outbound.multimodal.plain_text import parse_plain_text
from arbor.application.memory.commands import ConfirmInboxItem
from arbor.adapters.outbound.inmemory import (
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryPersonaRepository,
    InMemoryStores,
    InMemoryVectorIndex,
    FixtureEmbeddingClient,
    SeqIdGenerator,
)
from arbor.domain.memory.memory import InboxItem, MemoryType
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId


def test_plain_text_chunks_to_file_chunk_inbox():
    result = parse_plain_text("第一块\n\n第二块内容".encode(), "notes.md")
    assert result.parser == "plain_text"
    assert len(result.chunks) >= 1
    assert result.chunks[0].memory_type == "file_chunk"


def test_confirm_inbox_respects_memory_type():
    stores = InMemoryStores()
    tenant = TenantId("0a000000-0000-4000-a000-000000000001")
    persona = PersonaId("0a000000-0000-4000-a000-000000000010")
    inbox = InMemoryInboxRepository(stores)
    memories = InMemoryMemoryRepository(stores)
    inbox.add(
        InboxItem(
            id="inbox-1",
            tenant_id=tenant,
            persona_id=persona,
            kind="fact",
            payload={
                "text": "售后手册：7天无理由",
                "memory_type": "file_chunk",
                "source": "handbook.pdf",
            },
        )
    )
    confirm = ConfirmInboxItem(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        inbox=inbox,
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    item = confirm(
        tenant_id=tenant,
        user_id=UserId("0a000000-0000-4000-a000-000000000002"),
        persona_id=persona,
        inbox_id="inbox-1",
        capabilities=list(Capability),
    )
    assert item.type is MemoryType.FILE_CHUNK


def test_parse_document_md():
    parsed = parse_document("# 标题\n\n正文段落".encode(), "readme.md")
    assert parsed.media_kind in {"text", "document"}
    assert parsed.chunks
