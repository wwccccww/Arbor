from arbor.domain.persona.authorization import Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
THREAD = ThreadId("0a000000-0000-4000-a000-000000000030")


def test_send_message_keeps_attachments_off_memory_and_inbox():
    stores, send = _stack()
    before_memories = len(stores.memories)
    before_inbox = len(stores.inbox)
    out = send(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        persona_id=LINXIA,
        text="看看这个",
        capabilities=[Capability.CHAT, Capability.READ_MEMORY],
        attachments=[{"filename": "note.txt", "uri": "chat/note.txt"}],
    )
    assert out["attachments"] == [{"filename": "note.txt"}]
    thread = stores.threads[THREAD.value]
    user_msg = next(item for item in reversed(thread.messages) if item.role == "user")
    assert user_msg.content == "看看这个"
    assert user_msg.attachments == [{"filename": "note.txt", "uri": "chat/note.txt"}]
    assert len(stores.memories) == before_memories
    assert len(stores.inbox) == before_inbox
    assert all("note.txt" not in item.text for item in stores.memories.values())
