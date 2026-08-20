import pytest

from arbor.adapters.outbound.inmemory import (
    InMemoryStores,
    InMemoryTenantRepository,
    InMemoryUserRepository,
    SeqIdGenerator,
)
from arbor.application.identity.commands import (
    AddTenantMember,
    CreateTenant,
    DeleteTenant,
    ListMembers,
    ListTenants,
    PatchTenantMember,
)
from arbor.domain.errors import DomainError
from arbor.domain.identity.tenant import Membership, Role, Tenant
from arbor.domain.identity.user import User
from arbor.domain.shared.ids import TenantId, UserId

TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
OWNER = UserId("0a000000-0000-4000-a000-000000000002")
MEMBER = UserId("0a000000-0000-4000-a000-000000000003")


def _repos():
    stores = InMemoryStores()
    tenants = InMemoryTenantRepository(stores)
    users = InMemoryUserRepository(stores)
    users.save(User(id=OWNER, email="demo-a@arbor.eval"))
    users.save(User(id=MEMBER, email="member-a@arbor.eval"))
    tenants.save(
        Tenant(
            id=TENANT,
            name="演示租户A",
            memberships=[
                Membership(tenant_id=TENANT, user_id=OWNER, role=Role.OWNER),
                Membership(tenant_id=TENANT, user_id=MEMBER, role=Role.MEMBER),
            ],
        )
    )
    return tenants, users


def test_create_tenant_makes_caller_owner():
    tenants, _users = _repos()
    created = CreateTenant(tenants=tenants, ids=SeqIdGenerator())(user_id=OWNER, name="私人空间")
    assert created.name == "私人空间"
    assert created.member(OWNER).role is Role.OWNER
    listed = ListTenants(tenants)(user_id=OWNER)
    assert {item.name for item in listed} >= {"演示租户A", "私人空间"}


class _EmptyPersonas:
    def list(self, tenant_id):
        return []


class _BusyPersonas:
    def list(self, tenant_id):
        return [object()]


def test_only_owner_deletes_empty_tenant():
    tenants, _users = _repos()
    created = CreateTenant(tenants=tenants, ids=SeqIdGenerator())(user_id=OWNER, name="私人空间")
    with pytest.raises(DomainError) as forbidden:
        DeleteTenant(tenants=tenants, personas=_EmptyPersonas())(
            tenant_id=created.id,
            actor_id=MEMBER,
        )
    assert forbidden.value.code == "NOT_FOUND"
    tenants.save(
        Tenant(
            id=created.id,
            name=created.name,
            memberships=list(created.memberships)
            + [Membership(tenant_id=created.id, user_id=MEMBER, role=Role.MEMBER)],
        )
    )
    with pytest.raises(DomainError) as member:
        DeleteTenant(tenants=tenants, personas=_EmptyPersonas())(
            tenant_id=created.id,
            actor_id=MEMBER,
        )
    assert member.value.code == "FORBIDDEN_WORKSPACE"
    with pytest.raises(DomainError) as busy:
        DeleteTenant(tenants=tenants, personas=_BusyPersonas())(
            tenant_id=TENANT,
            actor_id=OWNER,
        )
    assert busy.value.code == "VALIDATION_ERROR"
    DeleteTenant(tenants=tenants, personas=_EmptyPersonas())(tenant_id=created.id, actor_id=OWNER)
    assert tenants.get(created.id) is None


def test_member_cannot_invite_or_list_members():
    tenants, users = _repos()
    with pytest.raises(DomainError) as exc:
        ListMembers(tenants, users)(tenant_id=TENANT, actor_id=MEMBER)
    assert exc.value.code == "FORBIDDEN_WORKSPACE"
    with pytest.raises(DomainError) as forbidden:
        AddTenantMember(tenants=tenants, users=users, ids=SeqIdGenerator())(
            tenant_id=TENANT,
            actor_id=MEMBER,
            email="c@d.com",
            role="member",
        )
    assert forbidden.value.code == "FORBIDDEN_WORKSPACE"


def test_owner_invites_and_cannot_demote_last_owner():
    tenants, users = _repos()
    added = AddTenantMember(tenants=tenants, users=users, ids=SeqIdGenerator())(
        tenant_id=TENANT,
        actor_id=OWNER,
        email="c@d.com",
        role="member",
    )
    items = ListMembers(tenants, users)(tenant_id=TENANT, actor_id=OWNER)
    emails = {item["user"]["email"] for item in items}
    assert "c@d.com" in emails
    assert added["role"] == "member"
    with pytest.raises(DomainError) as exc:
        PatchTenantMember(tenants)(
            tenant_id=TENANT,
            actor_id=OWNER,
            user_id=OWNER,
            role="member",
        )
    assert exc.value.code == "TENANT_OWNER_REQUIRED"
