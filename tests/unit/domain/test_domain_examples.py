from __future__ import annotations

import pytest
import yaml
from pathlib import Path

from arbor.domain.conversation.context_policy import ContextPolicy
from arbor.domain.conversation.thread import Citation, Message, Thread
from arbor.domain.errors import DomainError
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.identity.tenant import Membership, Role, Tenant
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import Capability
from arbor.domain.persona.persona import Persona, Profile
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId

CASES = yaml.safe_load((Path(__file__).resolve().parents[2] / "examples/domain.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_domain_examples(case):
    action = case["when"]["action"]
    if case["then"].get("error"):
        with pytest.raises(DomainError) as exc:
            _run(case, action)
        assert exc.value.code == case["then"]["error"]
        return
    _run(case, action)


def _run(case, action):
    given = case["given"]
    then = case["then"]
    if action == "change_tenant":
        p = Persona(
            id=PersonaId(given["persona"]["id"]),
            tenant_id=TenantId(given["persona"]["tenant_id"]),
            skin="companion",
            profile=Profile(display_name=given["persona"]["display_name"]),
        )
        p.change_tenant(TenantId(case["when"]["to"]))
        return
    if action == "append_message":
        thread = Thread(
            id=ThreadId(given["thread_id"]),
            tenant_id=TenantId("0a000000-0000-4000-a000-000000000001"),
            persona_id=PersonaId(given["persona_id"]),
        )
        thread.append_message(Message(role="user", content=case["when"]["text"]), can_chat=False)
        return
    if action == "build_context":
        profile = Profile(
            display_name=given["profile"]["display_name"],
            one_liner=given["profile"]["one_liner"],
            taboos=given["profile"]["taboos"],
            relationships=given["profile"]["relationships"],
        )
        slots = ContextPolicy().assemble(
            profile=profile,
            capabilities=[Capability(c) for c in given["capabilities"]],
            summary="",
            event_hits=[],
            memory_hits=[],
        )
        assert set(slots.profile) <= {"display_name", "one_liner"}
        for forbidden in then["slots_forbidden"]:
            assert forbidden not in slots.profile
        return
    if action == "rebind_persona":
        thread = Thread(
            id=ThreadId(given["thread"]["id"]),
            tenant_id=TenantId("t"),
            persona_id=PersonaId(given["thread"]["persona_id"]),
        )
        thread.rebind_persona(PersonaId(case["when"]["to"]))
        return
    if action == "attach_citation":
        mem = MemoryItem(
            id=MemoryId(given["citation_memory"]["id"]),
            tenant_id=TenantId("t"),
            persona_id=PersonaId(given["citation_memory"]["persona_id"]),
            text="x",
        )
        Citation(memory_id=mem.id).assert_persona(PersonaId(given["thread_persona"]), mem)
        return
    if action == "confirm_inbox_item":
        old = MemoryItem(
            id=MemoryId(given["active_fact"]["id"]),
            tenant_id=TenantId("t"),
            persona_id=PersonaId("p"),
            text=given["active_fact"]["text"],
        )
        inbox = InboxItem(
            id="i",
            tenant_id=old.tenant_id,
            persona_id=old.persona_id,
            kind="conflict",
            payload=given["inbox_item"]["payload"],
            conflicts_with=old.id,
        )
        new = MemoryItem(
            id=MemoryId("0a000000-0000-4000-a000-000000000308"),
            tenant_id=old.tenant_id,
            persona_id=old.persona_id,
            text=given["inbox_item"]["payload"]["text"],
        )
        inbox.confirm(new, old)
        assert old.status is MemoryStatus.SUPERSEDED
        assert new.status is MemoryStatus.ACTIVE
        assert str(new.supersedes.value) == then["new_supersedes"]
        return
    if action == "nothing_confirmed":
        assert given["profile"]["taboos"] == then["profile.taboos"]
        assert then["memory_writes"] == 0
        return
    if action == "add_edge":
        a = EventNode(
            id=EventId(given["from_event"]["id"]),
            tenant_id=TenantId("t"),
            persona_id=PersonaId(given["from_event"]["persona_id"]),
            title="a",
        )
        b = EventNode(
            id=EventId(given["to_event"]["id"]),
            tenant_id=TenantId("t"),
            persona_id=PersonaId(given["to_event"]["persona_id"]),
            title="b",
        )
        EventEdge.between(a, b, case["when"]["kind"])
        return
    if action == "demote_or_remove":
        owners = given["owners"]
        tenant = Tenant(
            id=TenantId(given["tenant_id"]),
            name="A",
            memberships=[
                Membership(tenant_id=TenantId(given["tenant_id"]), user_id=UserId(u), role=Role.OWNER)
                for u in owners
            ],
        )
        tenant.remove_member(UserId(case["when"]["user_id"]))
        return
    raise AssertionError(action)
