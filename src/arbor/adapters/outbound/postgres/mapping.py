from __future__ import annotations

from arbor.domain.conversation.thread import Thread
from arbor.domain.eventgraph.graph import EventEdge, EventNode
from arbor.domain.memory.memory import InboxItem, MemoryItem, MemoryStatus, MemoryType
from arbor.domain.persona.authorization import Capability, Grant, Persona, Profile, ToolPolicy
from arbor.domain.shared.ids import EventId, MemoryId, PersonaId, TenantId, ThreadId, UserId


def _text(value) -> str:
    return "" if value is None else str(value)


def _tool_policy_from_row(raw) -> ToolPolicy:
    if not raw or not isinstance(raw, dict):
        return ToolPolicy()
    allowed = raw.get("allowed_tools") or []
    return ToolPolicy(
        allowed_tools=[str(item) for item in allowed],
        notes=_text(raw.get("notes")),
    )


def persona_from_row(row: dict, grants: list[Grant]) -> Persona:
    taboos = row.get("taboos") or []
    relationships = row.get("relationships") or []
    return Persona(
        id=PersonaId(str(row["id"])),
        tenant_id=TenantId(str(row["tenant_id"])),
        skin=_text(row.get("skin")) or "companion",
        profile=Profile(
            display_name=_text(row.get("display_name")),
            one_liner=_text(row.get("one_liner")),
            personality=row.get("personality"),
            taboos=list(taboos),
            relationships=list(relationships),
            avatar=_text(row.get("avatar")),
        ),
        grants=grants,
        tool_policy=_tool_policy_from_row(row.get("tool_policy")),
    )


def grant_from_row(row: dict) -> Grant:
    caps = []
    for raw in row.get("capabilities") or []:
        caps.append(Capability(raw) if not isinstance(raw, Capability) else raw)
    return Grant(user_id=UserId(str(row["user_id"])), capabilities=caps)


def memory_from_row(row: dict) -> MemoryItem:
    event_id = row.get("event_id")
    thread_id = row.get("thread_id")
    supersedes = row.get("supersedes")
    source = row.get("source")
    return MemoryItem(
        id=MemoryId(str(row["id"])),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        text=_text(row.get("text")),
        type=MemoryType(row.get("type") or "fact"),
        status=MemoryStatus(row.get("status") or "active"),
        event_id=EventId(str(event_id)) if event_id else None,
        thread_id=ThreadId(str(thread_id)) if thread_id else None,
        supersedes=MemoryId(str(supersedes)) if supersedes else None,
        source=dict(source) if source else None,
    )


def event_from_row(row: dict) -> EventNode:
    happened = row.get("happened_at")
    return EventNode(
        id=EventId(str(row["id"])),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        title=_text(row.get("title")),
        summary=_text(row.get("summary")),
        type=_text(row.get("type")) or "daily",
        importance=int(row.get("importance") or 3),
        happened_at=happened.isoformat() if hasattr(happened, "isoformat") else happened,
        confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
    )


def edge_from_row(row: dict) -> EventEdge:
    return EventEdge(
        from_id=EventId(str(row["from_id"])),
        to_id=EventId(str(row["to_id"])),
        kind=_text(row["kind"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
    )


def thread_from_row(row: dict) -> Thread:
    return Thread(
        id=ThreadId(str(row["id"])),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        summary=_text(row.get("summary")),
    )


def inbox_from_row(row: dict) -> InboxItem:
    conflict = row.get("conflict_with")
    return InboxItem(
        id=_text(row["id"]),
        tenant_id=TenantId(str(row["tenant_id"])),
        persona_id=PersonaId(str(row["persona_id"])),
        kind=_text(row.get("kind")),
        payload=dict(row.get("payload") or {}),
        status=_text(row.get("status")) or "pending",
        conflicts_with=MemoryId(str(conflict)) if conflict else None,
    )
