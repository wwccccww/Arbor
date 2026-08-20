import os

import pytest

from arbor.domain.identity.tenant import Role
from arbor.domain.identity.user import User
from arbor.domain.shared.ids import TenantId, UserId
from arbor.env import database_url

pytestmark = pytest.mark.postgres

TENANT_A = TenantId("0a000000-0000-4000-a000-000000000001")
TENANT_B = TenantId("0b000000-0000-4000-a000-000000000001")
USER_A = UserId("0a000000-0000-4000-a000-000000000002")
USER_B = UserId("0b000000-0000-4000-a000-000000000002")


@pytest.mark.skipif(not (database_url() or os.environ.get("DATABASE_URL")), reason="Postgres contract tests need DATABASE_URL")
def test_list_tenants_stays_in_membership(pg):
    pg.users.save(User(id=USER_A, email="a@arbor.eval"))
    pg.users.save(User(id=USER_B, email="b@arbor.eval"))
    extra = User(id=UserId("c0000000-0000-4000-a000-000000000001"), email="extra@arbor.eval")
    pg.users.save(extra)
    tenant_a = pg.tenants.get(TENANT_A)
    tenant_b = pg.tenants.get(TENANT_B)
    if tenant_a.member(USER_A) is None:
        tenant_a.add_member(USER_A, Role.OWNER)
    tenant_a.add_member(extra.id, Role.MEMBER)
    pg.tenants.save(tenant_a)
    if tenant_b.member(USER_B) is None:
        tenant_b.add_member(USER_B, Role.OWNER)
        pg.tenants.save(tenant_b)
    assert {item.id for item in pg.tenants.list_for_user(USER_A)} == {TENANT_A}
    assert {item.id for item in pg.tenants.list_for_user(USER_B)} == {TENANT_B}
    assert extra.id not in {membership.user_id for membership in pg.tenants.get(TENANT_B).memberships}
