from __future__ import annotations

from arbor.domain.auth.credentials import hash_password, verify_password
from arbor.domain.identity.tenant import Membership, Role
from arbor.domain.shared.ids import TenantId, UserId

TOKENS = {
    "token-a": {
        "user_id": "0a000000-0000-4000-a000-000000000002",
        "tenant_id": "0a000000-0000-4000-a000-000000000001",
        "role": "owner",
        "email": "demo-a@arbor.eval",
    },
    "token-member": {
        "user_id": "0a000000-0000-4000-a000-000000000003",
        "tenant_id": "0a000000-0000-4000-a000-000000000001",
        "role": "member",
        "email": "member-a@arbor.eval",
    },
    "token-b": {
        "user_id": "0b000000-0000-4000-a000-000000000002",
        "tenant_id": "0b000000-0000-4000-a000-000000000001",
        "role": "owner",
        "email": "demo-b@arbor.eval",
    },
}

DEMO_PASSWORDS = {
    "demo-a@arbor.eval": "arbor-owner",
    "member-a@arbor.eval": "arbor-member",
    "demo-b@arbor.eval": "arbor-owner",
}

MEMBER_ID = UserId("0a000000-0000-4000-a000-000000000003")
DEMO_TENANT = TenantId("0a000000-0000-4000-a000-000000000001")
LINXIA_ID = "0a000000-0000-4000-a000-000000000010"


def demo_password_ok(email: str, password: str) -> bool:
    expected = DEMO_PASSWORDS.get((email or "").strip().lower())
    if not expected:
        return False
    import hmac

    return hmac.compare_digest(expected, password or "")


def profile_for_demo_email(email: str) -> dict | None:
    lowered = (email or "").strip().lower()
    for profile in TOKENS.values():
        if profile["email"] == lowered:
            return dict(profile)
    return None


def authenticate_user(users, tenants, email: str, password: str) -> dict | None:
    """Resolve a session profile from persisted users when Postgres is enabled."""
    from arbor.adapters.outbound.postgres.identity import PgUserRepository

    if not isinstance(users, PgUserRepository):
        return None
    user = users.get_by_email(email)
    if user is None:
        return None
    row = users.conn.execute(
        "SELECT password_hash FROM users WHERE id = %s::uuid",
        (user.id.value,),
    ).fetchone()
    stored = str(row["password_hash"] or "") if row else ""
    if not verify_password(password, stored):
        return None
    membership = tenants.conn.execute(
        """
        SELECT tenant_id, role
        FROM memberships
        WHERE user_id = %s::uuid
        ORDER BY tenant_id
        LIMIT 1
        """,
        (user.id.value,),
    ).fetchone()
    if membership is None:
        return None
    return {
        "user_id": user.id.value,
        "tenant_id": str(membership["tenant_id"]),
        "role": str(membership["role"]),
        "email": user.email,
    }


def ensure_demo_member(tenants, users) -> None:
    from arbor.domain.identity.user import User

    for profile in TOKENS.values():
        uid = UserId(profile["user_id"])
        tenant_id = TenantId(profile["tenant_id"])
        if users.get(uid) is None:
            users.save(User(id=uid, email=profile["email"]))
        if hasattr(users, "conn"):
            password = DEMO_PASSWORDS.get(profile["email"])
            if password:
                users.conn.execute(
                    """
                    UPDATE users SET password_hash = %s
                    WHERE id = %s::uuid AND password_hash IS NULL
                    """,
                    (hash_password(password), uid.value),
                )
        tenant = tenants.get(tenant_id)
        if tenant is None:
            continue
        role = Role(profile["role"])
        if tenant.member(uid) is None:
            tenant.memberships.append(Membership(tenant_id=tenant_id, user_id=uid, role=role))
            tenants.save(tenant)

    tenant = tenants.get(DEMO_TENANT)
    if tenant is None:
        return
    if users.get(MEMBER_ID) is None:
        users.save(User(id=MEMBER_ID, email="member-a@arbor.eval"))
    if hasattr(users, "conn"):
        users.conn.execute(
            """
            UPDATE users SET password_hash = %s
            WHERE id = %s::uuid AND password_hash IS NULL
            """,
            (hash_password(DEMO_PASSWORDS["member-a@arbor.eval"]), MEMBER_ID.value),
        )
    if tenant.member(MEMBER_ID) is None:
        tenant.memberships.append(
            Membership(tenant_id=DEMO_TENANT, user_id=MEMBER_ID, role=Role.MEMBER)
        )
        tenants.save(tenant)
