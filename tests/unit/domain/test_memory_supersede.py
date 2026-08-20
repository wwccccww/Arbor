import pytest

from arbor.domain.errors import DomainError
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.shared.ids import MemoryId, PersonaId, TenantId


def test_memory_supersede():
    old = MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000307"),
        tenant_id=TenantId("t"),
        persona_id=PersonaId("p"),
        text="林夏很喜欢猫",
        status=MemoryStatus.ACTIVE,
    )
    inbox = InboxItem(
        id="inb-1",
        tenant_id=old.tenant_id,
        persona_id=old.persona_id,
        kind="conflict",
        payload={"text": "林夏对猫毛过敏"},
        conflicts_with=old.id,
    )
    new = MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000308"),
        tenant_id=old.tenant_id,
        persona_id=old.persona_id,
        text="林夏对猫毛过敏",
        type=MemoryType.FACT,
    )
    inbox.confirm(new, old)
    assert old.status is MemoryStatus.SUPERSEDED
    assert new.status is MemoryStatus.ACTIVE
    assert new.supersedes == old.id


def test_profile_no_silent_update():
    from arbor.domain.persona.persona import Profile

    profile = Profile(display_name="林夏", taboos=["香菜"])
    inbox = InboxItem(
        id="inb-2",
        tenant_id=TenantId("t"),
        persona_id=PersonaId("p"),
        kind="fact",
        payload={"taboos": ["香菜", "洋葱"]},
        status="pending",
    )
    assert inbox.status == "pending"
    assert profile.taboos == ["香菜"]


def test_inbox_dismiss():
    inbox = InboxItem(
        id="inb-3",
        tenant_id=TenantId("t"),
        persona_id=PersonaId("p"),
        kind="fact",
        payload={"text": "临时"},
    )
    inbox.dismiss()
    assert inbox.status == "dismissed"
    with pytest.raises(DomainError) as exc:
        inbox.dismiss()
    assert exc.value.code == "CONFLICT_INBOX_STATE"
