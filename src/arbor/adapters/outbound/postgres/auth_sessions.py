from __future__ import annotations

import secrets

from arbor.adapters.outbound.auth_sessions import InMemoryAuthSessionStore


class PgAuthSessionStore:
    def __init__(self, conn, static_tokens: dict[str, dict] | None = None) -> None:
        self.conn = conn
        self._static = {k: dict(v) for k, v in (static_tokens or {}).items()}
        self._seed_static()

    def _seed_static(self) -> None:
        for access, profile in self._static.items():
            refresh = f"ref_static_{access}"
            self.conn.execute(
                """
                INSERT INTO auth_sessions (access_token, refresh_token, user_id, tenant_id, role, email)
                VALUES (%s, %s, %s::uuid, %s::uuid, %s, %s)
                ON CONFLICT (access_token) DO NOTHING
                """,
                (
                    access,
                    refresh,
                    profile["user_id"],
                    profile["tenant_id"],
                    profile["role"],
                    profile["email"],
                ),
            )

    def issue(self, profile: dict) -> dict:
        access = f"tok_{secrets.token_urlsafe(16)}"
        refresh = f"ref_{secrets.token_urlsafe(16)}"
        stored = dict(profile)
        self.conn.execute(
            """
            INSERT INTO auth_sessions (access_token, refresh_token, user_id, tenant_id, role, email)
            VALUES (%s, %s, %s::uuid, %s::uuid, %s, %s)
            """,
            (
                access,
                refresh,
                stored["user_id"],
                stored["tenant_id"],
                stored["role"],
                stored["email"],
            ),
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "user": {"id": stored["user_id"], "email": stored["email"]},
        }

    def get_profile(self, access_token: str) -> dict | None:
        static = self._static.get(access_token)
        if static is not None:
            return dict(static)
        row = self.conn.execute(
            """
            SELECT user_id, tenant_id, role, email
            FROM auth_sessions
            WHERE access_token = %s
            """,
            (access_token,),
        ).fetchone()
        if row is None:
            return None
        return {
            "user_id": str(row["user_id"]),
            "tenant_id": str(row["tenant_id"]),
            "role": str(row["role"]),
            "email": str(row["email"] or ""),
        }

    def refresh_session(self, refresh_token: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT access_token, user_id, tenant_id, role, email
            FROM auth_sessions
            WHERE refresh_token = %s
            """,
            (refresh_token,),
        ).fetchone()
        if row is None:
            return None
        profile = {
            "user_id": str(row["user_id"]),
            "tenant_id": str(row["tenant_id"]),
            "role": str(row["role"]),
            "email": str(row["email"] or ""),
        }
        self.conn.execute(
            "DELETE FROM auth_sessions WHERE access_token = %s",
            (row["access_token"],),
        )
        return self.issue(profile)

    def logout(self, refresh_token: str) -> None:
        row = self.conn.execute(
            "SELECT access_token FROM auth_sessions WHERE refresh_token = %s",
            (refresh_token,),
        ).fetchone()
        if row is None:
            return
        self.conn.execute(
            "DELETE FROM auth_sessions WHERE refresh_token = %s OR access_token = %s",
            (refresh_token, row["access_token"]),
        )


def auth_session_store(conn=None, static_tokens: dict[str, dict] | None = None):
    if conn is None:
        return InMemoryAuthSessionStore(static_tokens)
    return PgAuthSessionStore(conn, static_tokens)
