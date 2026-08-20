from __future__ import annotations

import pytest

from arbor.domain.conversation.context_policy import ContextPolicy
from arbor.domain.conversation.thread import Citation, Message, Thread
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.identity.tenant import Membership, Role, Tenant
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import Capability, Grant
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId


def test_authorization_persona_cannot_change_tenant():
    persona = Persona(
        id=PersonaId("0a000000-0000-4000-a000-000000000010"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        skin="companion",
        profile=Profile(display_name="林夏"),
    )
    with pytest.raises(DomainError) as exc:
        persona.change_tenant(TenantId("0b000000-0000-4000-a000-000000000001"))
    assert exc.value.code == "PERSONA_TENANT_IMMUTABLE"


def test_thread_chat_required():
    thread = Thread(
        id=ThreadId("0a000000-0000-4000-a000-000000000030"),
        tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    with pytest.raises(DomainError) as exc:
        thread.append_message(Message(role="user", content="你好"), can_chat=False)
    assert exc.value.code == "FORBIDDEN_CHAT"


def test_context_policy_no_read_memory_min_profile():
    profile = Profile(
        display_name="林夏",
        one_liner="住在杭州的陪伴助手",
        taboos=["香菜"],
        relationships=[{"name": "用户", "kind": "partner"}],
    )
    slots = ContextPolicy().assemble(
        profile=profile,
        capabilities=[Capability.CHAT],
        summary="secret",
        event_hits=[{"title": "x"}],
        memory_hits=[],
    )
    assert set(slots.profile) == {"display_name", "one_liner"}
    assert "taboos" not in slots.profile
    assert slots.injected_memory_ids == []


def test_thread_persona_bound():
    thread = Thread(
        id=ThreadId("t"),
        tenant_id=TenantId("a"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000010"),
    )
    with pytest.raises(DomainError) as exc:
        thread.rebind_persona(PersonaId("0a000000-0000-4000-a000-000000000020"))
    assert exc.value.code == "THREAD_PERSONA_IMMUTABLE"


def test_citation_cross_persona_forbidden():
    memory = MemoryItem(
        id=MemoryId("0a000000-0000-4000-a000-000000000401"),
        tenant_id=TenantId("a"),
        persona_id=PersonaId("0a000000-0000-4000-a000-000000000020"),
        text="手册",
    )
    cite = Citation(memory_id=memory.id)
    with pytest.raises(DomainError) as exc:
        cite.assert_persona(PersonaId("0a000000-0000-4000-a000-000000000010"), memory)
    assert exc.value.code == "CITATION_PERSONA_MISMATCH"


def test_tenant_owner_required():
    tenant = Tenant(
        id=TenantId("0a000000-0000-4000-a000-000000000001"),
        name="A",
        memberships=[
            Membership(
                tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
                user_id=UserId("0a000000-0000-4000-a000-000000000002"),
                role=Role.OWNER,
            )
        ],
    )
    with pytest.raises(DomainError) as exc:
        tenant.remove_member(UserId("0a000000-0000-4000-a000-000000000002"))
    assert exc.value.code == "TENANT_OWNER_REQUIRED"
