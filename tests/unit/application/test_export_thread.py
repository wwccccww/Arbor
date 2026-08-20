import pytest

from arbor.adapters.outbound.inmemory import (
    FixedClock,
    InMemoryAuditLogRepository,
    InMemoryPersonaRepository,
    InMemoryThreadRepository,
    SeqIdGenerator,
)
from arbor.application.audit.commands import RecordAudit
from arbor.application.audit.queries import ListAuditLogs
from arbor.application.conversation.threads import ExportThread
from arbor.domain.conversation.thread import Message
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, ThreadId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
THREAD = ThreadId("0a000000-0000-4000-a000-000000000030")


def test_export_thread_requires_chat_and_writes_audit():
    stores, _send = _stack()
    logs = InMemoryAuditLogRepository(stores)
    audit = RecordAudit(logs=logs, ids=SeqIdGenerator(), clock=FixedClock())
    threads = InMemoryThreadRepository(stores)
    thread = threads.get(TENANT, THREAD)
    thread.append_message(Message(role="user", content="还在吗"), can_chat=True)
    threads.save(thread)
    cmd = ExportThread(
        personas=InMemoryPersonaRepository(stores),
        threads=threads,
        auth=AuthorizationPolicy(),
        audit=audit,
    )
    with pytest.raises(DomainError) as hidden:
        cmd(
            tenant_id=TENANT,
            user_id=USER,
            thread_id=THREAD,
            capabilities=[Capability.READ_MEMORY],
        )
    assert hidden.value.code == "NOT_FOUND"
    exported = cmd(
        tenant_id=TENANT,
        user_id=USER,
        thread_id=THREAD,
        capabilities=list(Capability),
    )
    assert exported["id"] == THREAD.value
    assert exported["persona_id"] == LINXIA.value
    assert exported["messages"][0]["content"] == "还在吗"
    rows = ListAuditLogs(logs)(tenant_id=TENANT, workspace_admin=True, action="thread.export")
    assert len(rows) == 1
    assert rows[0].payload == {"message_count": 1}
    assert "还在吗" not in str(rows[0].payload)
