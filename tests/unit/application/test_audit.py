import pytest

from arbor.adapters.outbound.inmemory import (
    FixtureEmbeddingClient,
    InMemoryAuditLogRepository,
    InMemoryInboxRepository,
    InMemoryMemoryRepository,
    InMemoryObjectStorage,
    InMemoryPersonaRepository,
    InMemoryVectorIndex,
    FixedClock,
    SeqIdGenerator,
)
from arbor.application.audit.commands import RecordAudit
from arbor.application.audit.queries import ListAuditLogs
from arbor.application.memory.commands import ConfirmInboxItem, ImportArtifact
from arbor.application.persona.commands import PatchPersona
from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import InboxItem
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
OTHER = TenantId("0b000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
ZHOU = PersonaId("0a000000-0000-4000-a000-000000000020")


def _audit(stores):
    ids = SeqIdGenerator()
    logs = InMemoryAuditLogRepository(stores)
    record = RecordAudit(logs=logs, ids=ids, clock=FixedClock())
    return logs, record, ids


def test_list_audit_requires_workspace_admin():
    stores, _send = _stack()
    logs, _record, _ids = _audit(stores)
    query = ListAuditLogs(logs)
    with pytest.raises(DomainError) as exc:
        query(tenant_id=TENANT, workspace_admin=False)
    assert exc.value.code == "FORBIDDEN_WORKSPACE"


def test_patch_import_confirm_write_audit_rows():
    stores, _send = _stack()
    logs, record, ids = _audit(stores)
    PatchPersona(
        personas=InMemoryPersonaRepository(stores),
        auth=AuthorizationPolicy(),
        audit=record,
    )(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
        display_name="林夏改名",
    )
    ImportArtifact(
        personas=InMemoryPersonaRepository(stores),
        storage=InMemoryObjectStorage(stores),
        auth=AuthorizationPolicy(),
        audit=record,
    )(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        filename="notes.txt",
        data=b"x",
        capabilities=list(Capability),
    )
    InMemoryInboxRepository(stores).add(
        InboxItem(
            id="inbox-1",
            tenant_id=TENANT,
            persona_id=LINXIA,
            kind="fact",
            payload={"text": "确认这条"},
        )
    )
    memories = InMemoryMemoryRepository(stores)
    ConfirmInboxItem(
        personas=InMemoryPersonaRepository(stores),
        memories=memories,
        inbox=InMemoryInboxRepository(stores),
        vectors=InMemoryVectorIndex(stores, memories),
        embed=FixtureEmbeddingClient(),
        ids=ids,
        auth=AuthorizationPolicy(),
        audit=record,
    )(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        inbox_id="inbox-1",
        capabilities=list(Capability),
    )
    listed = ListAuditLogs(logs)(tenant_id=TENANT, workspace_admin=True)
    actions = [entry.action for entry in listed]
    assert actions == ["memory.confirm", "memory.import", "persona.update"]
    filtered = ListAuditLogs(logs)(tenant_id=TENANT, workspace_admin=True, action="persona.update")
    assert [entry.action for entry in filtered] == ["persona.update"]
    zhou_only = ListAuditLogs(logs)(tenant_id=TENANT, workspace_admin=True, persona_id=ZHOU)
    assert zhou_only == []
    other = ListAuditLogs(logs)(tenant_id=OTHER, workspace_admin=True)
    assert other == []
