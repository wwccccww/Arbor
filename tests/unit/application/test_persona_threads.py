import pytest

from arbor.adapters.outbound.inmemory import (
    InMemoryPersonaRepository,
    InMemoryThreadRepository,
    SeqIdGenerator,
)
from arbor.application.conversation.threads import CreateThread, ListThreads
from arbor.application.persona.commands import CreatePersona, PatchPersona
from arbor.application.persona.queries import ListPersonas
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import AuthorizationPolicy, Capability
from arbor.domain.shared.ids import PersonaId, TenantId, UserId
from tests.unit.application.test_send_message import USER, _stack

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA = PersonaId("0a000000-0000-4000-a000-000000000010")
ZHOU = PersonaId("0a000000-0000-4000-a000-000000000020")
MEMBER = UserId("0a000000-0000-4000-a000-000000000003")


def test_list_personas_filters_member_grants():
    stores, _send = _stack()
    query = ListPersonas(InMemoryPersonaRepository(stores))
    owner_items = query(tenant_id=TENANT, user_id=USER, workspace_admin=True)
    member_items = query(tenant_id=TENANT, user_id=MEMBER, workspace_admin=False)
    assert {p.id for p in owner_items} >= {LINXIA, ZHOU}
    assert [p.id for p in member_items] == []


def test_create_persona_requires_workspace_admin():
    stores, _send = _stack()
    cmd = CreatePersona(
        personas=InMemoryPersonaRepository(stores),
        ids=SeqIdGenerator(),
        auth=AuthorizationPolicy(),
    )
    with pytest.raises(DomainError) as exc:
        cmd(
            tenant_id=TENANT,
            user_id=MEMBER,
            workspace_admin=False,
            skin="companion",
            display_name="不该创建",
        )
    assert exc.value.code == "FORBIDDEN_WORKSPACE"
    created = cmd(
        tenant_id=TENANT,
        user_id=USER,
        workspace_admin=True,
        skin="companion",
        display_name="新林夏",
        taboos=["香菜"],
    )
    assert created.profile.display_name == "新林夏"
    assert created.profile.taboos == ["香菜"]


def test_create_thread_and_list():
    stores, _send = _stack()
    personas = InMemoryPersonaRepository(stores)
    threads = InMemoryThreadRepository(stores)
    create = CreateThread(personas=personas, threads=threads, ids=SeqIdGenerator(), auth=AuthorizationPolicy())
    listed = ListThreads(personas=personas, threads=threads, auth=AuthorizationPolicy())
    thread = create(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
    )
    items = listed(
        tenant_id=TENANT,
        user_id=USER,
        persona_id=LINXIA,
        capabilities=list(Capability),
    )
    assert any(item.id == thread.id for item in items)


def test_patch_persona_requires_admin():
    stores, _send = _stack()
    cmd = PatchPersona(personas=InMemoryPersonaRepository(stores), auth=AuthorizationPolicy())
    with pytest.raises(DomainError) as exc:
        cmd(
            tenant_id=TENANT,
            user_id=MEMBER,
            persona_id=LINXIA,
            capabilities=[Capability.CHAT],
            one_liner="不该改",
        )
    assert exc.value.code == "FORBIDDEN_WORKSPACE"
