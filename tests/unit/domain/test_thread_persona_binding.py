from arbor.domain.conversation.thread import Thread
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId


def test_thread_persona_binding():
    thread = Thread(
        id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        tenant_id=TenantId("a"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    thread.rebind_persona(PersonaId("0a000000-0000-4000-a000-000000000010"))
    assert thread.persona_id.value.endswith("010")
