from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantId:
    value: str


@dataclass(frozen=True, slots=True)
class UserId:
    value: str


@dataclass(frozen=True, slots=True)
class PersonaId:
    value: str


@dataclass(frozen=True, slots=True)
class MemoryId:
    value: str


@dataclass(frozen=True, slots=True)
class EventId:
    value: str


@dataclass(frozen=True, slots=True)
class ThreadId:
    value: str
