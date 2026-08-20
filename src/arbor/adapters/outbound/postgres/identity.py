from __future__ import annotations

from arbor.domain.identity.tenant import Membership, Role, Tenant
from arbor.domain.identity.user import User
from arbor.domain.shared.ids import TenantId, UserId


class PgTenantRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, tenant_id: TenantId) -> Tenant | None:
        row = self.conn.execute(
            "SELECT id, name FROM tenants WHERE id = %s::uuid",
            (tenant_id.value,),
        ).fetchone()
        if row is None:
            return None
        members = self.conn.execute(
            """
            SELECT user_id, role
            FROM memberships
            WHERE tenant_id = %s::uuid
            ORDER BY role, user_id
            """,
            (tenant_id.value,),
        ).fetchall()
        return Tenant(
            id=TenantId(str(row["id"])),
            name=str(row["name"] or ""),
            memberships=[
                Membership(
                    tenant_id=TenantId(str(row["id"])),
                    user_id=UserId(str(item["user_id"])),
                    role=Role(item["role"]),
                )
                for item in members
            ],
        )

    def list_for_user(self, user_id: UserId) -> list[Tenant]:
        rows = self.conn.execute(
            """
            SELECT tenant_id
            FROM memberships
            WHERE user_id = %s::uuid
            ORDER BY tenant_id
            """,
            (user_id.value,),
        ).fetchall()
        return [tenant for tenant_id in (TenantId(str(row["tenant_id"])) for row in rows) if (tenant := self.get(tenant_id))]

    def save(self, tenant: Tenant) -> None:
        self.conn.execute(
            """
            INSERT INTO tenants (id, name)
            VALUES (%s::uuid, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """,
            (tenant.id.value, tenant.name),
        )
        self.conn.execute("DELETE FROM memberships WHERE tenant_id = %s::uuid", (tenant.id.value,))
        for membership in tenant.memberships:
            self.conn.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role)
                VALUES (%s::uuid, %s::uuid, %s)
                """,
                (tenant.id.value, membership.user_id.value, membership.role.value),
            )

    def delete(self, tenant_id: TenantId) -> None:
        self.conn.execute("DELETE FROM memberships WHERE tenant_id = %s::uuid", (tenant_id.value,))
        self.conn.execute("DELETE FROM tenants WHERE id = %s::uuid", (tenant_id.value,))


class PgUserRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, user_id: UserId) -> User | None:
        row = self.conn.execute(
            "SELECT id, email FROM users WHERE id = %s::uuid",
            (user_id.value,),
        ).fetchone()
        return _user_from_row(row)

    def get_by_email(self, email: str) -> User | None:
        row = self.conn.execute(
            "SELECT id, email FROM users WHERE lower(email) = lower(%s)",
            ((email or "").strip(),),
        ).fetchone()
        return _user_from_row(row)

    def save(self, user: User) -> None:
        self.conn.execute(
            """
            INSERT INTO users (id, email)
            VALUES (%s::uuid, %s)
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
            """,
            (user.id.value, user.email),
        )


def _user_from_row(row) -> User | None:
    if row is None:
        return None
    return User(id=UserId(str(row["id"])), email=str(row["email"] or ""))
