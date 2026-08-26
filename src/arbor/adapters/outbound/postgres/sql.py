from __future__ import annotations

from arbor.domain.errors import DomainError


def require_tenant(tenant_id) -> None:
    if tenant_id is None:
        raise DomainError("VALIDATION_ERROR", "tenant_id required")


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


def set_app_tenant(conn, tenant_id: str | None) -> None:
    if tenant_id:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))


def tenant_matches_policy_sql(column: str = "tenant_id") -> str:
    return (
        f"(current_setting('app.tenant_id', true) IS NULL "
        f"OR current_setting('app.tenant_id', true) = '' "
        f"OR {column} = current_setting('app.tenant_id')::uuid)"
    )
