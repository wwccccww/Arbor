from arbor.application.conversation.compress_thread_summary import compress_thread_summary
from arbor.domain.conversation.thread import Message, Thread
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId


def test_compress_thread_summary_after_enough_messages():
    messages: list[Message] = []
    for i in range(3):
        messages.append(Message(role="user", content=f"消息{i}"))
        messages.append(Message(role="assistant", content=f"回复{i}"))
    thread = Thread(
        id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        messages=messages,
    )

    class StubReasoner:
        def summarize(self, dialogue: str, prior: str = "") -> str:
            return "压缩后的摘要"

    summary = compress_thread_summary(thread, StubReasoner())
    assert summary == "压缩后的摘要"
