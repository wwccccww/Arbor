from arbor.domain.conversation.thread import Citation, Message, Thread
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId, ThreadId


def test_thread_messages_roundtrip(pg):
    thread = Thread(
        id=ThreadId("c0000000-0000-4000-a000-000000000030"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        summary="新会话",
        messages=[
            Message(role="user", content="还在吗", attachments=[{"filename": "note.txt", "uri": "chat/note.txt"}]),
            Message(
                role="assistant",
                content="在",
                citations=[Citation(memory_id=MemoryId("0a000000-0000-4000-a000-000000000302"))],
            ),
        ],
    )
    pg.threads.save(thread)
    loaded = pg.threads.get(thread.tenant_id, thread.id)
    assert loaded is not None
    assert [m.role for m in loaded.messages] == ["user", "assistant"]
    assert loaded.messages[0].content == "还在吗"
    assert loaded.messages[0].attachments == [{"filename": "note.txt", "uri": "chat/note.txt"}]
    assert loaded.messages[1].citations[0].memory_id.value == "0a000000-0000-4000-a000-000000000302"
    listed = pg.threads.list(thread.tenant_id, thread.persona_id)
    assert any(item.id == thread.id for item in listed)
