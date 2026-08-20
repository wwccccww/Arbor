import pytest

from arbor.adapters.outbound.inmemory import (
    InMemoryObjectStorage,
    InMemoryPersonaRepository,
    InMemoryThreadRepository,
)
from arbor.application.conversation.threads import GetChatAttachment
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
THREAD = ThreadId("0a000000-0000-4000-a000-000000000030")
PAYLOAD = b"chat-file-bytes"


def test_get_chat_attachment_requires_chat_and_stored_bytes():
    stores, send = _stack()
    before_memories = len(stores.memories)
    storage = InMemoryObjectStorage(stores)
    uri = storage.put("chat/linxia/note.txt", PAYLOAD)
    send(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        persona_id=LINXIA,
        text="看看这个",
        capabilities=list(Capability),
        attachments=[{"filename": "note.txt", "uri": uri}],
    )
    query = GetChatAttachment(
        personas=InMemoryPersonaRepository(stores),
        threads=InMemoryThreadRepository(stores),
        storage=storage,
        auth=AuthorizationPolicy(),
    )
    found = query(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        filename="note.txt",
        capabilities=list(Capability),
    )
    assert found == {"filename": "note.txt", "data": PAYLOAD}
    with pytest.raises(DomainError) as hidden:
        query(
            tenant_id=TENANT,
            user_id=USER,
            thread_id=THREAD,
            filename="note.txt",
            capabilities=[Capability.READ_MEMORY],
        )
    assert hidden.value.code == "NOT_FOUND"
    send(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        persona_id=LINXIA,
        text="只有名字",
        capabilities=list(Capability),
        attachments=[{"filename": "ghost.png"}],
    )
    with pytest.raises(DomainError) as missing:
        query(
            tenant_id=TENANT,
            user_id=USER,
            thread_id=THREAD,
            filename="ghost.png",
            capabilities=list(Capability),
        )
    assert missing.value.code == "NOT_FOUND"
    assert len(stores.memories) == before_memories
