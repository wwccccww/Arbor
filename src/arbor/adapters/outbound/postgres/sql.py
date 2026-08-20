from __future__ import annotations

from arbor.domain.errors import DomainError


def require_tenant(tenant_id) -> None:
    if tenant_id is None:
        raise DomainError("VALIDATION_ERROR", "tenant_id required")


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vector) + "]"
