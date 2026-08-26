from __future__ import annotations

from arbor.adapters.inbound.http.serialization import caps_for
from arbor.domain.errors import DomainError
from arbor.domain.persona.authorization import Capability


def require_read(persona, user: dict) -> list[Capability]:
    caps = caps_for(persona, user)
    if Capability.READ_MEMORY not in caps:
        raise DomainError("NOT_FOUND", "not found")
    return caps


def require_write(persona, user: dict) -> list[Capability]:
    caps = caps_for(persona, user)
    if Capability.WRITE_MEMORY not in caps and Capability.ADMIN not in caps:
        raise DomainError("NOT_FOUND", "not found")
    return caps
